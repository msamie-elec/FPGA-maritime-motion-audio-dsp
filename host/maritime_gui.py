"""Desktop before/after demonstration for the maritime FPGA motion FIR.

Windows: python host/maritime_gui.py
The GUI never labels software model output as physical FPGA output.
The board needs its existing bitstream; GUI has no remote JTAG programmer.
"""
from __future__ import annotations

import csv
import json
import queue
import sys
import threading
import traceback
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import cv2
import numpy as np
from PIL import Image, ImageTk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0,str(Path(__file__).resolve().parent))
from motion_estimation import inspect_video
from gui_pipeline import run_pipeline
from generate_synthetic_clip import generate
from fixed_point_golden import FirReference
from fpga_serial_client import run_batch
from stabilize_video import inputs_from_csv
from affine_stabilization import read_path
from prepare_natural_footage import prepare_natural_footage, probe_raw


class MaritimeGUI:
    def __init__(self, window: tk.Tk):
        self.window = window
        self.window.title('Maritime FPGA DSP | Camera Motion Stabilisation')
        self.window.geometry('1440x850')
        self.window.minsize(1150,690)
        self.window.configure(bg='#edf3f8')
        self.events: queue.Queue = queue.Queue()
        self._help_window = None
        self._footage_window = None
        self._analysis_window = None
        self.source: Path | None = None
        self.trajectory: Path | None = None
        self.result = None
        self.capture = None
        # One player handles either a raw input (left panel only) or a
        # processed side-by-side MP4. Timers are cancelled on pause/reload.
        self._playback_kind = None  # 'source' or 'pair'
        self._play_after_id = None
        self.frames = 0
        self.frame_idx = 0
        self.fps = 30.0
        self.playing = False
        self.busy = False
        self._seek_enabled = True
        self._img_left = None
        self._img_right = None
        self.comport = tk.StringVar(value='')
        self.video_info = tk.StringVar(value='No video selected')
        self.motion_mode = tk.StringVar(value='Natural footage: automatic OpenCV motion estimation (no CSV or synthetic shake)')
        self.input_kind = 'NATURAL'
        self.image_metric = tk.StringVar(value='Independent image stability: not assessed')
        self.validation = tk.StringVar(value='No hardware verification yet')
        self.status = tk.StringVar(value='Ready. Choose a video or generate the example clip.')
        self.stat_x = tk.StringVar(value='—')
        self.stat_y = tk.StringVar(value='—')
        self.stat_roll = tk.StringVar(value='—')
        self.profile = tk.StringVar(value='Normal')
        self.stat_frames = tk.StringVar(value='—')
        self.stat_run = tk.StringVar(value='—')
        self.axis = tk.StringVar(value='X')
        self.seek_pos = tk.DoubleVar(value=0)
        self._build()
        self.refresh_ports()
        self.window.after(70,self._poll_events)
        self.window.protocol('WM_DELETE_WINDOW',self._close)
        self.window.bind('<F1>',lambda event:self.show_help())

    def _build(self):
        """Three-tab UI: practical operation, full-size analysis, and help.

        All firmware, video, UART, and reference-processing operations are
        preserved from v0.7; only the presentation and navigation change.
        """
        C = dict(bg='#f2f5f8', panel='#ffffff', navy='#17354d', teal='#007f99',
                 text='#243d50', muted='#60778a', line='#dce4eb', pale='#eef4f7')
        self.palette = C
        style = ttk.Style(self.window)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('TFrame', background=C['panel'])
        style.configure('TLabel', background=C['panel'], foreground=C['text'],
                        font=('Segoe UI', 10))
        style.configure('TButton', padding=(9, 6), font=('Segoe UI', 9),
                        background='#edf2f6', foreground=C['text'], bordercolor=C['line'])
        style.map('TButton', background=[('active', '#dce9f1'),
                                         ('disabled', '#f5f6f8')])
        style.configure('Accent.TButton', padding=(11, 6), font=('Segoe UI', 9, 'bold'),
                        background=C['teal'], foreground='white', bordercolor=C['teal'])
        style.map('Accent.TButton', background=[('active', '#00677e'),
                                                ('disabled', '#a9bec8')],
                  foreground=[('disabled', '#e8f1f4')])
        style.configure('TCombobox', padding=4, font=('Segoe UI', 9))
        style.configure('TNotebook', background=C['bg'], borderwidth=0)
        style.configure('TNotebook.Tab', font=('Segoe UI', 10, 'bold'),
                        padding=(22, 9), background='#e5ecf2', foreground=C['text'])
        style.map('TNotebook.Tab', background=[('selected', C['panel']),
                                                ('active', '#d8eaf2')],
                  foreground=[('selected', C['teal'])])
        style.configure('TRadiobutton', font=('Segoe UI', 10), background=C['panel'],
                        foreground=C['text'])

        # Compact application header, rather than multiple numbered sections.
        header=tk.Frame(self.window,bg=C['navy'],height=52)
        header.pack(fill='x'); header.pack_propagate(False)
        tk.Label(header,text='MARITIME  /  CAMERA STABILISATION',
                 font=('Segoe UI',15,'bold'),bg=C['navy'],fg='#f7fbfd').pack(side='left',padx=18)
        tk.Label(header,text='ARTY A7   •   X / Y / ROLL FIR',
                 font=('Segoe UI',9),bg=C['navy'],fg='#bed3de').pack(side='right',padx=18)

        self.main_tabs=ttk.Notebook(self.window)
        self.main_tabs.pack(fill='both',expand=True,padx=9,pady=(6,4))
        self.implementation_tab=ttk.Frame(self.main_tabs)
        self.assessment_tab=ttk.Frame(self.main_tabs)
        self.help_tab=ttk.Frame(self.main_tabs)
        self.main_tabs.add(self.implementation_tab,text='Implementation')
        self.main_tabs.add(self.assessment_tab,text='Assessment')
        self.main_tabs.add(self.help_tab,text='Help')

        # All primary actions sit on ONE toolbar row. Specialised lab features
        # are kept accessible in File, not crowding out the video.
        toolbar=ttk.Frame(self.implementation_tab)
        toolbar.pack(side='top',fill='x',padx=9,pady=(9,7))
        self.open_btn=ttk.Button(toolbar,text='Open video',command=self.choose_video)
        self.open_btn.pack(side='left',padx=(0,4))
        ttk.Button(toolbar,text='Reset view',command=self.reset_view).pack(side='left',padx=(0,10))
        ttk.Label(toolbar,text='COM').pack(side='left',padx=(0,4))
        self.port_entry=ttk.Combobox(toolbar,textvariable=self.comport,width=7,state='normal')
        self.port_entry.pack(side='left',padx=(0,4))
        ttk.Button(toolbar,text='Detect ports',command=self.refresh_ports).pack(side='left',padx=(0,4))
        self.test_btn=ttk.Button(toolbar,text='Verify FPGA',command=self.hardware_test)
        self.test_btn.pack(side='left',padx=(0,10))
        self.hw_btn=ttk.Button(toolbar,text='Stabilise using FPGA',style='Accent.TButton',
                               command=lambda:self.process(True))
        self.hw_btn.pack(side='left',padx=(0,4))
        self.sw_btn=ttk.Button(toolbar,text='Software preview',command=lambda:self.process(False))
        self.sw_btn.pack(side='left',padx=(0,10))
        ttk.Label(toolbar,text='Smoothing').pack(side='left',padx=(0,4))
        self.profile_combo=ttk.Combobox(toolbar,textvariable=self.profile,
                                        values=['Normal','Strong'],state='readonly',width=8)
        self.profile_combo.pack(side='left')
        # Retain the specialised controls as real File menu actions.
        self.demo_btn=ttk.Button(self.implementation_tab,text='Synthetic test',command=self.make_demo)
        self.csv_btn=ttk.Button(self.implementation_tab,text='Lab trajectory',command=self.choose_csv)
        self.real_btn=ttk.Button(self.implementation_tab,text='Prepare recording',command=self.real_footage_dialog)

        # A single, small input-information line. Avoid displaying lengthy
        # processing descriptions on top of the video or in large type.
        info=tk.Frame(self.implementation_tab,bg=C['panel'])
        info.pack(fill='x',padx=9,pady=(0,6))
        tk.Label(info,textvariable=self.video_info,font=('Segoe UI',9),bg=C['panel'],
                 fg=C['muted'],anchor='w').pack(fill='x',padx=9,pady=3)
        self.motion_mode_label = None  # Details are in the Help tab and evidence.

        # The complete remaining workspace belongs to the two synchronized
        # video panels. No analysis charts share this vertical space.
        video_area=tk.Frame(self.implementation_tab,bg=C['panel'])
        video_area.pack(fill='both',expand=True,padx=9,pady=(0,6))
        video_area.grid_rowconfigure(0,weight=1)
        video_area.grid_columnconfigure(0,weight=1,uniform='video')
        video_area.grid_columnconfigure(1,weight=1,uniform='video')
        frames=[]
        for column,title in [(0,'ORIGINAL VIDEO'),(1,'STABILISED VIDEO')]:
            pane=tk.Frame(video_area,bg='#142b3c')
            pane.grid(row=0,column=column,sticky='nsew',padx=(0,4) if column==0 else (4,0))
            heading=tk.Label(pane,text=title,font=('Segoe UI',10,'bold'),
                             bg='#142b3c',fg='#dde9ef')
            heading.pack(fill='x',pady=(6,2))
            if column==1:
                self.after_title=heading
            frames.append(pane)
        self.left=ttk.Label(frames[0],text='Open a video to begin',anchor='center',
                            background='#142b3c',foreground='#ffffff',
                            font=('Segoe UI',11))
        self.right=ttk.Label(frames[1],text='Process a video to see the result',
                             anchor='center',background='#142b3c',foreground='#ffffff',
                             font=('Segoe UI',11))
        self.left.pack(fill='both',expand=True)
        self.right.pack(fill='both',expand=True)
        self._video_resize_job=None
        for view in (self.left,self.right):
            view.bind('<Configure>',self._on_video_resize,add='+')

        playback=ttk.Frame(self.implementation_tab)
        playback.pack(side='bottom',fill='x',padx=10,pady=(1,8))
        self.play_btn=ttk.Button(playback,text='▶ Play',command=self.toggle_play,state='disabled')
        self.play_btn.pack(side='left',padx=(0,8))
        self.seek=ttk.Scale(playback,variable=self.seek_pos,from_=0,to=100,orient='horizontal')
        self.seek.pack(side='left',fill='x',expand=True,padx=4)
        self.seek.bind('<ButtonPress-1>',self._seek_press)
        self.seek.bind('<ButtonRelease-1>',self._seek_release)
        self.frame_text=ttk.Label(playback,text='0 / 0',width=11)
        self.frame_text.pack(side='left',padx=(12,5))
        ttk.Button(playback,text='Results folder',command=self.open_output).pack(side='right',padx=(8,0))

        # Assessment tab: large plotting region, all verification data together.
        assess_top=ttk.Frame(self.assessment_tab)
        assess_top.pack(fill='x',padx=12,pady=(12,5))
        tiles=ttk.Frame(assess_top)
        tiles.pack(fill='x')
        for name,value in [('X reduction',self.stat_x),('Y reduction',self.stat_y),
                           ('Roll reduction',self.stat_roll),('Frames',self.stat_frames),
                           ('Elapsed',self.stat_run)]:
            tile=tk.Frame(tiles,bg=C['pale'])
            tile.pack(side='left',fill='x',expand=True,padx=3)
            tk.Label(tile,text=name,font=('Segoe UI',9),bg=C['pale'],fg=C['muted']).pack(anchor='w',padx=12,pady=(7,0))
            tk.Label(tile,textvariable=value,font=('Segoe UI',16,'bold'),bg=C['pale'],fg=C['navy']).pack(anchor='w',padx=12,pady=(0,7))
        ttk.Label(assess_top,textvariable=self.validation).pack(fill='x',padx=6,pady=(9,1))
        ttk.Label(assess_top,textvariable=self.image_metric).pack(fill='x',padx=6,pady=(0,4))

        # Small view controls; the selected plot fills the remaining tab height.
        plotbar=ttk.Frame(self.assessment_tab)
        plotbar.pack(fill='x',padx=14,pady=(3,4))
        self.assess_view=tk.StringVar(value='Motion curves')
        for title in ('Motion curves','Frequency spectrum','Image stability','Evidence log'):
            ttk.Radiobutton(plotbar,text=title,variable=self.assess_view,value=title,
                            command=self._show_assessment_view).pack(side='left',padx=(0,17))
        ttk.Label(plotbar,text='Axis:').pack(side='left',padx=(14,5))
        for axis in ('X','Y','ROLL'):
            ttk.Radiobutton(plotbar,text=axis,variable=self.axis,value=axis,
                            command=self.draw_plots).pack(side='left',padx=(0,8))

        self.assessment_content=ttk.Frame(self.assessment_tab)
        self.assessment_content.pack(fill='both',expand=True,padx=14,pady=(0,12))
        self._assess_widgets={}
        for name in ('Motion curves','Frequency spectrum','Image stability'):
            fig=Figure(figsize=(12,6),dpi=110,facecolor='#ffffff')
            ax=fig.add_subplot(111)
            canvas=FigureCanvasTkAgg(fig,master=self.assessment_content)
            canvas.get_tk_widget().configure(bg='#ffffff')
            self._assess_widgets[name]=canvas.get_tk_widget()
            if name=='Motion curves':
                self.chartfig,self.chartax,self.chartcanvas=fig,ax,canvas
            elif name=='Frequency spectrum':
                self.specfig,self.specax,self.speccanvas=fig,ax,canvas
            else:
                self.imgfig,self.imgax,self.imgcanvas=fig,ax,canvas
        self.log=scrolledtext.ScrolledText(self.assessment_content,wrap='word',
                                           font=('Consolas',10),bg='#f8fafc',
                                           fg=C['text'],relief='flat',padx=12,pady=12)
        self.log.configure(state='disabled')
        self._assess_widgets['Evidence log']=self.log
        self._show_assessment_view()

        # Help is a proper third tab with readable sections, not another modal
        # pop-up that obscures the active video.
        help_frame=tk.Frame(self.help_tab,bg=C['panel'])
        help_frame.pack(fill='both',expand=True,padx=18,pady=15)
        self.help_text=scrolledtext.ScrolledText(help_frame,wrap='word',borderwidth=0,
                           font=('Segoe UI',11),bg='#ffffff',fg=C['text'],
                           padx=20,pady=16,spacing1=2,spacing3=7)
        self.help_text.pack(fill='both',expand=True)
        self.help_text.tag_configure('heading',font=('Segoe UI',16,'bold'),
                                      foreground=C['navy'],spacing1=8,spacing3=13)
        self.help_text.tag_configure('subheading',font=('Segoe UI',12,'bold'),
                                      foreground=C['teal'],spacing1=12,spacing3=6)
        self.help_text.tag_configure('body',font=('Segoe UI',11),
                                      foreground=C['text'],lmargin1=4,lmargin2=4)
        self.help_text.tag_configure('step',font=('Segoe UI',11),
                                      foreground=C['text'],lmargin1=20,lmargin2=34,spacing3=10)
        self._help_sections={}
        def add_section(title,parts):
            start=self.help_text.index('end-1c')
            self.help_text.insert('end',title+'\n','subheading')
            self._help_sections[title]=start
            for item in parts:
                self.help_text.insert('end',item+'\n','step')
            self.help_text.insert('end','\n')
        self.help_text.insert('end','Operator guide\n','heading')
        self.help_text.insert('end','Arty A7-35T  |  Buffered USB-UART FIR processing  |  X / Y / roll\n\n','body')
        add_section('Quick start',[
            '1. Program the Arty A7 with the project bitstream in Vivado Hardware Manager after power-up.',
            '2. Select the board COM port (previously COM4), then click Verify FPGA (3 bit-exact tests).',
            '3. Choose Open video for a prepared 30 fps video, or File → Prepare original recording.',
            '4. Choose Normal smoothing first, then Stabilise using FPGA.',
            '5. Play the synchronized videos. Open Assessment for large motion and stability plots.'
        ])
        add_section('Program the FPGA in Vivado',[
            'Connect the Arty A7 via USB, power the board and launch Vivado 2025.2.1.',
            'If you have no bitstream, rebuild from the project root:',
            r'  & "C:\AMDDesignTools\2025.2.1\Vivado\bin\vivado.bat" -mode batch -source scripts/build_maritime_bitstream.tcl',
            r'Open Hardware Manager → Open target → Auto Connect → Program Device.',
            r'Select build\vivado_maritime_a7\maritime_a7.runs\impl_1\arty_a7_maritime_top.bit.',
            'After successful programming, select its USB-UART COM port. BTN0 resets the FPGA logic; Reset view resets only the GUI.'
        ])
        add_section('Implementation controls',[
            'Open video — load a compatible MP4/MOV/AVI/M4V; 30 fps, up to 1280×720, 18–496 frames.',
            'Reset view — clear displayed results; does not program or reset the board.',
            'COM / Detect ports — choose the physical USB serial port and refresh the list.',
            'Verify FPGA — send three reference cases and compare every returned result bit-for-bit.',
            'Stabilise using FPGA — estimate X/Y/roll on the PC, filter via the physical FPGA and warp frames on the PC.',
            'Software preview — run the same pipeline in Python, explicitly NOT hardware verification.',
            'Smoothing: Normal = one 17-tap FIR pass per axis (3 jobs). Strong = two consecutive FIR passes per axis (6 jobs).',
            'Strong is not automatically better: it can increase cropping and suppress intentional pans.',
            'File menu → Prepare recording / Synthetic demo / Lab CSV are additional tools, not required for a normal video run.'
        ])
        add_section('Assessment',[
            'Motion curves — original vs filtered X, Y or roll trajectory over time.',
            'Frequency spectrum — compare attenuation across camera-motion frequencies.',
            'Image stability — independent image-content registration before vs after (can be INCONCLUSIVE).',
            'Evidence log — inspect bit-exact verification, output files, quality warnings and errors.',
            'Numeric FIR improvements do not prove visibly improved images. Look at the videos and independent measurement.'
        ])
        add_section('Project scope',[
            'The PC estimates camera motion and warps frames. The FPGA filters numeric X/Y/roll trajectories only.',
            'This is an offline 30 fps demonstration; no camera/video signal is streamed directly through the FPGA.',
            'Moving waves/ships, blur, limited background texture and perspective changes can reduce effectiveness.',
            'Use licensed, genuinely recorded shaky maritime footage for final industrial evidence.'
        ])
        self.help_text.configure(state='disabled')

        footer=tk.Frame(self.window,bg=C['navy'],height=27)
        footer.pack(side='bottom',fill='x');footer.pack_propagate(False)
        tk.Label(footer,textvariable=self.status,anchor='w',font=('Segoe UI',9),
                 fg='#e9f3f7',bg=C['navy']).pack(fill='both',padx=12)

        menu=tk.Menu(self.window,font=('Segoe UI',9))
        fm=tk.Menu(menu,tearoff=False,font=('Segoe UI',9))
        fm.add_command(label='Open video…',command=self.choose_video)
        fm.add_command(label='Prepare original recording…',command=self.real_footage_dialog)
        fm.add_separator()
        fm.add_command(label='Generate synthetic test clip',command=self.make_demo)
        fm.add_command(label='Load lab trajectory CSV…',command=self.choose_csv)
        fm.add_separator();fm.add_command(label='Exit',command=self._close)
        menu.add_cascade(label='File',menu=fm)
        menu.add_command(label='Assessment',command=lambda:self.main_tabs.select(self.assessment_tab))
        menu.add_command(label='Help',command=self.show_help)
        self.window.configure(menu=menu)
        self.window.bind('<Control-o>',lambda event:self.choose_video())
        self.draw_image_metric(); self.draw_plots()

    def _show_assessment_view(self):
        """Show one full-height graph, not several postage-stamp plot panels."""
        if not hasattr(self,'_assess_widgets'):
            return
        for widget in self._assess_widgets.values():
            widget.pack_forget()
        self._assess_widgets[self.assess_view.get()].pack(fill='both',expand=True)

    def _on_video_resize(self,event=None):
        """Re-render at the new full-height size after a window resize."""
        if self._video_resize_job is not None:
            try:self.window.after_cancel(self._video_resize_job)
            except tk.TclError:pass
        self._video_resize_job=self.window.after(180,self._refresh_video_size)

    def _refresh_video_size(self):
        self._video_resize_job=None
        if self.capture and self.frames:
            self._show_frame(self.frame_idx)
        elif self.source:
            self._show_source_frame()

    def focus_panel(self,which):
        self.main_tabs.select(self.assessment_tab if which=='analysis' else self.implementation_tab)

    def open_analysis_window(self):
        self.main_tabs.select(self.assessment_tab)

    def show_help(self,tab:str|None=None):
        self.main_tabs.select(self.help_tab)
        if tab:
            heading='Program the FPGA in Vivado' if tab=='Program Arty A7' else tab
            pos=self._help_sections.get(heading)
            if pos:
                self.help_text.see(pos)

    def real_footage_dialog(self):
        """Select and normalise a genuine recording; never inject vibration."""
        if self.busy:return
        win=tk.Toplevel(self.window)
        self._footage_window=win
        win.title('Import natural-shake maritime recording')
        win.geometry('760x405');win.minsize(660,380)
        body=ttk.Frame(win,padding=18);body.pack(fill='both',expand=True)
        ttk.Label(body,text='Import a naturally shaky camera recording',font=('Segoe UI',16,'bold')).pack(anchor='w',pady=(0,10))
        explain=('Choose your own real video recorded on a moving vessel. We will take a short clip, '
            'normalise the frame rate to 30 fps, preserve aspect ratio, and leave the actual camera motion untouched. '
            'No synthetic shake, trajectory CSV, or simulated camera movement is added. '
            'The application then estimates movement automatically from the original frames.')
        ttk.Label(body,text=explain,wraplength=690,justify='left').pack(anchor='w',pady=(0,10))
        field=ttk.Frame(body);field.pack(fill='x',pady=8)
        ttk.Label(field,text='Start time (seconds):').pack(side='left')
        startvar=tk.StringVar(value='0')
        ttk.Entry(field,textvariable=startvar,width=8).pack(side='left',padx=8)
        ttk.Label(field,text='Export duration: 5 seconds (maximum 150 frames)').pack(side='left',padx=10)
        ttk.Label(body,text='The source must contain enough stationary background texture. In some sea-only clips the motion estimate may be inconclusive. This will be reported rather than hidden.',wraplength=690,foreground='#8b4c35').pack(anchor='w',pady=(10,7))
        def choose():
            filename=filedialog.askopenfilename(parent=win,title='Choose the ORIGINAL recorded video',
                filetypes=[('Camera recordings','*.mp4 *.mov *.avi *.m4v *.webm *.mkv'),('All files','*.*')])
            if not filename:return
            try:
                starttime=float(startvar.get())
                if starttime<0:raise ValueError('Start must not be negative')
                probe_raw(Path(filename))
            except Exception as e:
                messagebox.showerror('Invalid footage',str(e),parent=win);return
            win.destroy()
            self._set_busy(True)
            self.status.set('Importing original camera recording without adding shake…')
            threading.Thread(target=self._natural_import_worker,args=(Path(filename),starttime),daemon=True).start()
        ttk.Button(body,text='Choose ORIGINAL recording and prepare',style='Accent.TButton',command=choose).pack(anchor='w',pady=12)
        ttk.Button(body,text='Cancel',command=win.destroy).pack(anchor='e')

    def _natural_import_worker(self,path:Path,start_s:float):
        try:
            import datetime
            tag=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            folder=ROOT/'build'/'natural_maritime_clips'/tag
            data=prepare_natural_footage(path,folder/'natural_input_30fps.mp4',start_s=start_s)
            self.events.put(('natural_import',data))
        except Exception as e:
            self.events.put(('error',(str(e),traceback.format_exc())))

    def _log(self,message):
        self.log.configure(state='normal')
        self.log.insert('end',message+'\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def refresh_ports(self):
        try:
            from serial.tools import list_ports
            ports=sorted([p.device for p in list_ports.comports()])
        except ImportError:
            ports=[]
        self.port_entry['values']=ports
        if ports and self.comport.get().upper() not in [p.upper() for p in ports]:
            self.comport.set(ports[0])
        self._log('Available serial ports: '+(', '.join(ports) if ports else 'none; install pyserial or connect the board'))

    def _validate_selected(self):
        if self.source is None:raise ValueError('Choose a video or generate the ship demo first.')
        return inspect_video(self.source)

    def choose_video(self):
        path=filedialog.askopenfilename(title='Select short 30-fps ship camera video',filetypes=[('Video files','*.mp4 *.mov *.avi *.m4v'),('All files','*.*')])
        if not path:return
        try:info=inspect_video(Path(path))
        except Exception as e:messagebox.showerror('Video not supported',str(e));return
        self.source=Path(path)
        self.trajectory=None
        self.motion_mode.set('NATURAL CAMERA MOTION: OpenCV automatic estimation; no CSV, no injected shake')
        self.input_kind='NATURAL'
        self.video_info.set(f'{self.source.name} | {info.width}×{info.height} | {info.fps:.2f} fps | {info.frames} frames')
        self._clear_result()
        self._show_source_frame()
        self.status.set('Original video ready to play. Stabilise using FPGA to compare with the corrected video.')
        self._log(f'Loaded input video {self.source} | {info.frames} frames')

    def make_demo(self):
        if self.busy:return
        try:
            path=ROOT/'build'/'gui_demo_source'
            v,t=generate(path,duration=5.0,fps=30)
            self.source=v;self.trajectory=t;self.input_kind='SYNTHETIC'
            info=inspect_video(v)
            self.video_info.set(f'Synthetic ship observation | {info.width}×{info.height} | 30 fps | {info.frames} frames')
            self.motion_mode.set('Known synthetic camera-motion ground truth (controlled verification)')
            self._clear_result();self._show_source_frame()
            self._log(f'Generated synthetic ship clip: {v}')
            self.status.set('Synthetic demo loaded. Ready for FPGA hardware processing.')
        except Exception as e:messagebox.showerror('Demo generation failed',str(e))

    def choose_csv(self):
        if self.source is None:
            messagebox.showinfo('Select video first','Choose a video before loading its trajectory CSV.');return
        if self.input_kind!='SYNTHETIC':
            messagebox.showinfo('Not permitted for natural footage',
                'Natural footage must use automatic OpenCV motion estimation. CSV trajectories are reserved for controlled synthetic/lab tests.');return
        path=filedialog.askopenfilename(title='Select camera motion CSV',filetypes=[('CSV files','*.csv')])
        if not path:return
        try:
            info=inspect_video(self.source)
            x,y=inputs_from_csv(Path(path))
            if len(x)!=info.frames or len(y)!=info.frames:
                raise ValueError(f'CSV has {len(x)} rows; expected {info.frames}.')
        except Exception as e:messagebox.showerror('Trajectory invalid',str(e));return
        self.trajectory=Path(path)
        self.motion_mode.set(f'SYNTHETIC LAB TEST: given motion CSV {self.trajectory.name} (OpenCV skipped)')
        self._clear_result();self._show_source_frame();self._log(f'Loaded trajectory {path}')

    def _set_busy(self,v):
        self.busy=v
        state='disabled' if v else 'normal'
        for widget in [self.hw_btn,self.sw_btn,self.demo_btn,self.open_btn,self.csv_btn,self.test_btn,self.real_btn]:
            widget.configure(state=state)

    def process(self,hardware:bool):
        if self.busy:return
        try:self._validate_selected()
        except Exception as e:messagebox.showerror('No valid input',str(e));return
        port=self.comport.get().strip().upper() if hardware else None
        if hardware and not port:
            messagebox.showerror('No COM port','Connect the programmed Arty A7 and select its UART COM port (COM4 in your successful test).');return
        if not hardware and not messagebox.askyesno('Software only','This mode will NOT communicate with the FPGA and will be labelled SOFTWARE REFERENCE ONLY. Continue?'):
            return
        self._clear_result()
        self._set_busy(True)
        self.status.set(('Sending motion data to the real Arty A7 on '+port if hardware else 'Running software-only preview')+' …')
        self.validation.set('Processing in progress — no results yet')
        base=ROOT/'build'/'gui_runs'
        import datetime
        dest=base/(datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+('_hardware' if hardware else '_software'))
        t=threading.Thread(target=self._process_thread,args=(self.source,self.trajectory,dest,port,self.profile.get()),daemon=True)
        t.start()

    def _process_thread(self,source,trajectory,dest,port,profile):
        try:self.events.put(('result',run_pipeline(source,trajectory,dest,port,profile=profile)))
        except Exception as e:self.events.put(('error',(str(e),traceback.format_exc())))

    def hardware_test(self):
        if self.busy:return
        port=self.comport.get().strip().upper()
        if not port:
            messagebox.showwarning('No COM port','Select your Arty A7 UART port first.');return
        self._set_busy(True)
        self.status.set('Running physical FPGA 3-case test on '+port+' …')
        threading.Thread(target=self._hardware_test_thread,args=(port,),daemon=True).start()

    def _hardware_test_thread(self,port):
        try:
            cases={'impulse':[32768]+[0]*31,'negative_dc':[-3840]*64,
                   'mixed_sign':[(-1 if i%2 else 1)*(23000+(i*8899)%33000) for i in range(80)]}
            for idx,(name,samples) in enumerate(cases.items(),1):
                expected=FirReference().process(samples)
                got=run_batch(port,samples,idx)
                if got!=expected:raise AssertionError(f'Hardware FIR mismatch in {name}')
                self.events.put(('info',f'PASS PHYSICAL FPGA {name}: {len(samples)} bit-exact samples'))
            self.events.put(('hardware_pass',port))
        except Exception as e:self.events.put(('error',(str(e),traceback.format_exc())))

    def _poll_events(self):
        try:
            while True:
                kind,payload=self.events.get_nowait()
                if kind=='info':self._log(payload)
                elif kind=='hardware_pass':
                    self._set_busy(False)
                    self.validation.set(f'PHYSICAL FPGA UART/FIR TEST PASS — {payload}: 3/3 cases, bit-exact')
                    self.status.set('Hardware connected and numerical test passed. Select a video and process it.')
                elif kind=='error':
                    self._set_busy(False)
                    message,detail=payload
                    self._log('ERROR: '+detail)
                    self.validation.set('FAILED / UNVERIFIED — no hardware success claim')
                    self.status.set('Processing failed. Open Assessment → Evidence log for details.')
                    messagebox.showerror('Processing failed',message)
                elif kind=='natural_import':
                    self._set_busy(False)
                    self.source=Path(payload[0]);self.trajectory=None;self.input_kind='NATURAL'
                    info=inspect_video(self.source)
                    self.video_info.set(f'NATURAL VIDEO (USER SUPPLIED) | {info.width}×{info.height} | {info.fps:.1f} fps | {info.frames} frames')
                    self.motion_mode.set('NATURAL CAMERA MOVEMENT: estimate trajectory from footage; no artificial shake or CSV')
                    self._clear_result();self._show_source_frame()
                    self.status.set('Natural recording prepared. Ready for automatic motion estimation and physical FPGA filtering.')
                    self._log('Natural footage prepared without synthetic shake: '+str(self.source))
                    self._log('Source provenance: '+str(self.source.parent/(self.source.stem+'_source_provenance.json')))
                elif kind=='result':
                    self._set_busy(False)
                    self._accept_result(payload)
        except queue.Empty:pass
        self.window.after(70,self._poll_events)

    def _accept_result(self,result):
        self.result=result
        if hasattr(self,'after_title'):
            self.after_title.configure(text='FPGA FILTERED — BIT-EXACT' if result.metrics.get('hardware_verified') else 'SOFTWARE PREVIEW — NOT FPGA')
        m=result.metrics
        self.stat_x.set(f"{m['x']['reduction_pct']:.1f}%")
        self.stat_y.set(f"{m['y']['reduction_pct']:.1f}%")
        self.stat_roll.set(f"{m['theta']['reduction_pct']:.1f}%" if "theta" in m else "N/A")
        self.stat_frames.set(str(m['frames']))
        self.stat_run.set(f'{result.elapsed_s:.2f} s')
        if m.get('hardware_verified'):
            self.validation.set(f"PHYSICAL FPGA — BIT-EXACT VERIFIED  |  Port {m['physical_port']}  |  30% shake target: {'PASS' if m['pass_target_30pct'] else 'NOT MET'}")
        else:
            self.validation.set('SOFTWARE REFERENCE ONLY — not FPGA hardware evidence')
        q=m.get('image_stability',{})
        if q.get('status')=='MEASURED':
            self.image_metric.set(f"Independent image-content: {q['reduction_pct']:+.1f}% jitter reduction | {m.get('visual_outcome','UNASSESSED')} | {m.get('crop',{}).get('area_retained_pct','N/A')}% area retained")
        else:
            self.image_metric.set('Independent image-content stability: INCONCLUSIVE — do not claim visual improvement')
        self._log('RESULT: '+json.dumps(m,indent=2))
        if m.get('motion_quality_warnings'):
            self._log('MOTION ESTIMATION WARNING: '+', '.join(m['motion_quality_warnings']))
        if m.get('crop',{}).get('warning'):
            self._log('CROP WARNING: '+m['crop']['warning'])
        self._log('MP4 saved to: '+str(result.side_by_side))
        self.status.set('Completed. Play the two videos together, inspect curves, or open output folder.')
        self.draw_plots()
        self.draw_image_metric()
        self._open_pair_video(result.side_by_side)

    def _open_playback_video(self, path: Path, kind: str) -> None:
        """Open one source video or one already-rendered side-by-side video.

        Playback is independent of FIR processing: original footage is
        immediately playable in the left panel, with a right-side placeholder.
        """
        if kind not in ('source', 'pair'):
            raise ValueError(f'Unsupported playback kind: {kind}')
        self._release_video()
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            messagebox.showerror('Video playback', f'Could not open video: {path}')
            return
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if count < 1:
            cap.release()
            messagebox.showerror('Video playback', 'The selected video has no readable frames.')
            return
        self.capture = cap
        self.frames = count
        self._playback_kind = kind
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        self.fps = fps if np.isfinite(fps) and fps > 0 else 30.0
        self.seek.configure(to=max(0, count - 1))
        self.play_btn.configure(state='normal', text='▶ Play')
        if kind == 'source':
            self.right.configure(image='', text='Process this video to see the stabilised result')
            self._img_right = None
        self._show_frame(0)

    def _open_pair_video(self, path: Path) -> None:
        self._open_playback_video(path, 'pair')

    def _show_source_frame(self) -> None:
        if not self.source:
            self._release_video()
            return
        self._open_playback_video(self.source, 'source')

    def _render_label(self,label,frame,which):
        if frame is None:return
        ih,iw=frame.shape[:2]
        maxw=max(320,label.winfo_width()-8)
        maxh=max(150,label.winfo_height()-8)
        scale=min(maxw/max(1,iw),maxh/max(1,ih),3.0)
        sw,sh=max(1,int(iw*scale)),max(1,int(ih*scale))
        if sw != iw or sh != ih:frame=cv2.resize(frame,(sw,sh),interpolation=cv2.INTER_AREA)
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        img=ImageTk.PhotoImage(Image.fromarray(rgb))
        label.configure(image=img,text='')
        if which=='left':self._img_left=img
        else:self._img_right=img

    def _show_frame(self, index: int) -> None:
        if self.capture is None or self.frames < 1:
            return
        index = int(max(0, min(self.frames - 1, index)))
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = self.capture.read()
        if not ok or frame is None:
            # Do not allow a failed decode to leave the timer running forever.
            self._pause_playback()
            self.status.set(f'Could not decode video frame {index + 1}.')
            return
        if self._playback_kind == 'pair':
            w = frame.shape[1] // 2
            self._render_label(self.left, frame[:, :w], 'left')
            self._render_label(self.right, frame[:, w:], 'right')
        else:
            self._render_label(self.left, frame, 'left')
        self.frame_idx = index
        self.seek_pos.set(index)
        self.frame_text.configure(text=f'{index + 1} / {self.frames}')

    def _cancel_play_timer(self) -> None:
        if self._play_after_id is not None:
            try:
                self.window.after_cancel(self._play_after_id)
            except tk.TclError:
                pass
            self._play_after_id = None

    def _pause_playback(self) -> None:
        self.playing = False
        self._cancel_play_timer()
        if self.capture is not None and self.frames > 0 and self.frame_idx >= self.frames - 1:
            self.play_btn.configure(text='↻ Replay')
        else:
            self.play_btn.configure(text='▶ Play')

    def _schedule_play_tick(self) -> None:
        if self.playing and self._play_after_id is None:
            interval_ms = max(15, round(1000.0 / self.fps))
            self._play_after_id = self.window.after(interval_ms, self._play_tick)

    def toggle_play(self) -> None:
        if self.capture is None or self.frames < 1:
            return
        if self.playing:
            self._pause_playback()
            return
        # Replay automatically from frame 0 after reaching the final frame.
        if self.frame_idx >= self.frames - 1:
            self._show_frame(0)
        self.playing = True
        self.play_btn.configure(text='❚❚ Pause')
        self._schedule_play_tick()

    def _play_tick(self) -> None:
        # The Tk timer fires only while video is playing. No old timer can
        # advance a newly loaded clip after switching source/processing mode.
        self._play_after_id = None
        if not self.playing or self.capture is None:
            return
        next_frame = self.frame_idx + 1
        if next_frame >= self.frames:
            self._pause_playback()
            return
        self._show_frame(next_frame)
        if self.playing:
            if self.frame_idx == self.frames - 1:
                self._pause_playback()
            else:
                self._schedule_play_tick()

    def _seek_press(self, event=None) -> None:
        # Scrubbing pauses the video; releasing the slider shows that frame.
        if self.playing:
            self._pause_playback()

    def _seek_release(self, event=None) -> None:
        if self.capture is not None:
            self._show_frame(round(self.seek_pos.get()))
            self._pause_playback()

    def draw_image_metric(self):
        ax=self.imgax;ax.clear()
        q=self.result.metrics.get('image_stability',{}) if self.result else {}
        if q.get('status')=='MEASURED':
            values=[q['before']['rms_high_frequency_registration_px'],
                    q['after']['rms_high_frequency_registration_px']]
            ax.bar(['Original video','Stabilised video'],values)
            ax.set_ylabel('Independent image jitter proxy (px RMS)')
            ax.set_title(f"Independent phase-correlation result: {q['reduction_pct']:+.1f}% jitter change")
            ax.grid(axis='y',alpha=.2)
        else:
            ax.text(.5,.5,'Independent image-content check: '+('INCONCLUSIVE' if q else 'Not run'),
                ha='center',va='center',transform=ax.transAxes)
            ax.set_axis_off()
        self.imgfig.subplots_adjust(left=.10,right=.96,bottom=.20,top=.85)
        self.imgcanvas.draw_idle()

    def draw_plots(self):
        axis=self.axis.get().lower()
        ax=self.chartax;bx=self.specax
        ax.clear();bx.clear()
        if self.result is None:
            ax.text(.5,.5,'Camera-motion curves will appear after filtering',ha='center',va='center',transform=ax.transAxes)
            bx.text(.5,.5,'Frequency spectrum will appear after filtering',ha='center',va='center',transform=bx.transAxes)
        else:
            x,y=inputs_from_csv(self.result.trajectory)
            try:
                path=read_path(self.result.trajectory) if axis=='roll' else None
            except (ValueError,KeyError):path=None
            if axis=='roll' and path is None:
                ax.text(.5,.5,'Roll trajectory requires v0.7 automatically estimated video',ha='center',va='center',transform=ax.transAxes)
                bx.text(.5,.5,'No roll data in this legacy test',ha='center',va='center',transform=bx.transAxes)
                self.chartcanvas.draw_idle();self.speccanvas.draw_idle();return
            a=path['theta'] if axis=='roll' else {'x':x,'y':y}[axis]
            b=self.result.filtered_trajectory['theta' if axis=='roll' else axis]
            t=np.arange(len(a))/30.0
            raw=np.asarray(a,dtype=float)/256
            fil=np.asarray(b,dtype=float)/256
            ax.plot(t,raw,label='Original camera motion',color='#557d98',linewidth=1.7)
            ax.plot(t,fil,label='FPGA-filtered' if self.result.metrics.get('hardware_verified') else 'Software-reference filtered',color='#05879b',linewidth=2.25)
            ax.set(xlabel='Video time (seconds)',ylabel=('Roll (degrees)' if axis=='roll' else f'{axis.upper()} camera displacement (pixels)'),title=f'{axis.upper()}-axis trajectory')
            ax.grid(True,alpha=.25);ax.legend(fontsize=8)
            def amp(q):
                # Remove DC so spectral change focuses on shaking rather than position offset.
                return 20*np.log10(np.maximum(1e-8,np.abs(np.fft.rfft(q-np.mean(q))))/max(1,len(q)))
            freq=np.fft.rfftfreq(len(raw),d=1/30.0)
            bx.plot(freq,amp(raw),label='Original trajectory',color='#557d98',linewidth=1.7)
            bx.plot(freq,amp(fil),label='Filtered trajectory',color='#05879b',linewidth=2.25)
            bx.set(xlabel='Motion frequency (Hz)',ylabel='Relative magnitude (dB)',title=f'{axis.upper()}-axis camera motion spectrum')
            bx.grid(True,alpha=.25);bx.legend(fontsize=8)
        for axes in (ax,bx):
            axes.spines['top'].set_visible(False)
            axes.spines['right'].set_visible(False)
            axes.tick_params(axis='both',labelsize=10,colors='#4a6476')
            axes.title.set_fontsize(13)
            axes.xaxis.label.set_fontsize(10)
            axes.yaxis.label.set_fontsize(10)
        self.chartfig.subplots_adjust(left=.09,right=.975,bottom=.21,top=.85)
        self.specfig.subplots_adjust(left=.09,right=.975,bottom=.21,top=.85)
        self.chartcanvas.draw_idle();self.speccanvas.draw_idle()

    def _clear_result(self):
        self._release_video()
        self.result=None
        if hasattr(self,'after_title'): self.after_title.configure(text='AFTER PROCESSING')
        for v in [self.stat_x,self.stat_y,self.stat_roll,self.stat_frames,self.stat_run]:v.set('—')
        self.validation.set('No FPGA verification for current selection')
        self.image_metric.set('Independent image stability: not assessed')
        self.draw_plots()
        self.draw_image_metric()
        self.play_btn.configure(state='disabled')
        self.frame_text.configure(text='0 / 0')

    def reset_view(self):
        if self.busy:
            messagebox.showwarning('Busy','Cannot reset view during an active UART/video job.');return
        self._clear_result()
        if self.source:self._show_source_frame()
        self.status.set('View cleared. FPGA hardware itself is unchanged; use BTN0 for a physical reset if required.')
        self._log('GUI reset view (does NOT reset the FPGA).')

    def open_output(self):
        if not self.result:
            messagebox.showinfo('No output','Run filtering to create an output folder.');return
        import os
        import subprocess
        folder=str(self.result.output_dir)
        if sys.platform=='win32':os.startfile(folder)
        elif sys.platform=='darwin':subprocess.Popen(['open',folder])
        else:subprocess.Popen(['xdg-open',folder])

    def _release_video(self) -> None:
        self.playing = False
        self._cancel_play_timer()
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        self._playback_kind = None
        self.frames = 0
        self.frame_idx = 0
        if hasattr(self, 'play_btn'):
            self.play_btn.configure(text='▶ Play', state='disabled')
            self.seek_pos.set(0)
            self.frame_text.configure(text='0 / 0')

    def _close(self):
        if self.busy and not messagebox.askyesno('Job in progress','A UART or processing operation is active. Close anyway?'):
            return
        self._release_video();self.window.destroy()


def _enable_windows_dpi_awareness():
    """Avoid blurry OS-scaled Tk text on high-DPI Windows monitors."""
    if sys.platform!='win32': return
    try:
        import ctypes
        # Per-monitor v2: fallback to Windows 8.1 awareness and then system DPI.
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try: ctypes.windll.user32.SetProcessDPIAware()
        except Exception: pass


def main():
    _enable_windows_dpi_awareness()
    try:
        root=tk.Tk()
        MaritimeGUI(root)
        root.mainloop()
    except tk.TclError as e:
        raise SystemExit('No desktop display available. Run on your Windows laptop with Tkinter.') from e

if __name__ == '__main__':main()
