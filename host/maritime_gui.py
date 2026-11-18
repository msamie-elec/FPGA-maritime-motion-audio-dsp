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
from gui_help import open_help
from prepare_natural_footage import prepare_natural_footage, probe_raw


class MaritimeGUI:
    def __init__(self, window: tk.Tk):
        self.window = window
        self.window.title('Maritime FPGA DSP | Camera Motion Stabilisation')
        self.window.geometry('1490x990')
        self.window.minsize(1120,760)
        self.window.configure(bg='#edf3f8')
        self.events: queue.Queue = queue.Queue()
        self._help_window = None
        self._footage_window = None
        self._analysis_window = None
        self.source: Path | None = None
        self.trajectory: Path | None = None
        self.result = None
        self.capture = None
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
        self.profile = tk.StringVar(value='Strong')
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
        """Responsive desktop dashboard: resizable video/analysis workspace."""
        C = dict(bg='#edf3f8', panel='#ffffff', navy='#122e45', teal='#087f9b',
                 text='#17334a', muted='#587084', line='#d7e3eb', pale='#eaf4f7')
        self.palette=C
        s=ttk.Style(self.window)
        try: s.theme_use('clam')
        except tk.TclError: pass
        s.configure('TFrame',background=C['panel'])
        s.configure('TLabel',background=C['panel'],foreground=C['text'],font=('Segoe UI',11))
        s.configure('TButton',padding=(13,9),font=('Segoe UI',11),background='#edf2f6',foreground=C['text'],bordercolor=C['line'])
        s.map('TButton',background=[('active','#dbe8f0'),('disabled','#f3f5f7')])
        s.configure('Accent.TButton',padding=(16,10),font=('Segoe UI',11,'bold'),
                    foreground='#ffffff',background=C['teal'],bordercolor=C['teal'])
        s.map('Accent.TButton',background=[('active','#08647b'),('disabled','#a9bcc5')],
              foreground=[('disabled','#e6eef2')])
        s.configure('TCombobox',padding=7,font=('Segoe UI',11))
        s.configure('TNotebook',background=C['panel'],borderwidth=0)
        s.configure('TNotebook.Tab',font=('Segoe UI',11,'bold'),padding=(17,11),background='#e7eef3',foreground=C['muted'])
        s.map('TNotebook.Tab',background=[('selected',C['panel']),('active','#d8ebf3')],foreground=[('selected',C['navy'])])
        s.configure('TRadiobutton',font=('Segoe UI',11),background=C['panel'],foreground=C['text'])

        def label(parent,text,weight='normal',size=11,fg=None,bg=None,**kwargs):
            return tk.Label(parent,text=text,font=('Segoe UI',size,weight),
                            fg=fg or C['text'],bg=bg or C['panel'],**kwargs)
        # Header is intentionally compact to give the analytics real screen space.
        top=tk.Frame(self.window,bg=C['navy'],height=78)
        top.pack(fill='x');top.pack_propagate(False)
        label(top,'MARITIME  /  CAMERA STABILISATION',size=19,weight='bold',fg='#ffffff',bg=C['navy']).pack(side='left',padx=24)
        self.header_pill=label(top,'ARTIX-7  •  FPGA FIR  •  OFFLINE X/Y/ROLL',size=10,weight='bold',fg='#bbebf4',bg=C['navy'])
        self.header_pill.pack(side='right',padx=26)

        # Input and board controls are grouped together and do not grow vertically.
        bar=tk.Frame(self.window,bg=C['panel'],highlightbackground=C['line'],highlightthickness=1)
        bar.pack(fill='x',padx=18,pady=(13,9))
        caption=tk.Frame(bar,bg=C['panel']);caption.pack(fill='x',padx=16,pady=(9,3))
        label(caption,'01   INPUT & BOARD CONNECTION',weight='bold',size=12,fg=C['navy']).pack(side='left')
        ttk.Button(caption,text='Help / Steps   F1',command=self.show_help).pack(side='right',padx=(6,0))
        ttk.Button(caption,text='Reset view',command=self.reset_view).pack(side='right')

        r1=tk.Frame(bar,bg=C['panel']);r1.pack(fill='x',padx=14,pady=(5,4))
        self.open_btn=ttk.Button(r1,text='Open video…',command=self.choose_video)
        self.open_btn.pack(side='left',padx=(0,7))
        self.real_btn=ttk.Button(r1,text='Import natural footage…',command=self.real_footage_dialog)
        self.real_btn.pack(side='left',padx=5)
        self.demo_btn=ttk.Button(r1,text='Synthetic test clip',command=self.make_demo)
        self.demo_btn.pack(side='left',padx=5)
        self.csv_btn=ttk.Button(r1,text='Lab trajectory CSV…',command=self.choose_csv)
        self.csv_btn.pack(side='left',padx=5)
        label(r1,'No shake is added to natural footage',fg=C['muted'],size=10).pack(side='right',padx=6)

        r2=tk.Frame(bar,bg=C['panel']);r2.pack(fill='x',padx=16,pady=(4,5))
        label(r2,'ARTY A7',weight='bold',size=10,fg=C['muted']).pack(side='left',padx=(0,8))
        self.port_entry=ttk.Combobox(r2,textvariable=self.comport,width=9,state='normal')
        self.port_entry.pack(side='left')
        ttk.Button(r2,text='Detect COM ports',command=self.refresh_ports).pack(side='left',padx=7)
        self.test_btn=ttk.Button(r2,text='Verify connection & FIR',command=self.hardware_test)
        self.test_btn.pack(side='left',padx=(0,8))
        self.hw_btn=ttk.Button(r2,text='Stabilise using FPGA',style='Accent.TButton',command=lambda:self.process(True))
        self.hw_btn.pack(side='left',padx=6)
        self.sw_btn=ttk.Button(r2,text='Software preview',command=lambda:self.process(False))
        self.sw_btn.pack(side='left',padx=6)
        label(r2,'Profile',weight='bold',size=10,fg=C['muted']).pack(side='left',padx=(15,6))
        self.profile_combo=ttk.Combobox(r2,textvariable=self.profile,values=['Normal','Strong'],state='readonly',width=9)
        self.profile_combo.pack(side='left',padx=(0,3))
        info=tk.Frame(bar,bg=C['panel']);info.pack(fill='x',padx=16,pady=(1,9))
        label(info,'VIDEO  ',fg=C['teal'],weight='bold',size=9).pack(side='left')
        tk.Label(info,textvariable=self.video_info,font=('Segoe UI',10),fg=C['text'],bg=C['panel'],anchor='w').pack(side='left')
        tk.Label(info,textvariable=self.motion_mode,font=('Segoe UI',9),fg=C['muted'],bg=C['panel'],anchor='e').pack(side='right',padx=5)

        # Core fix: a draggable sash with independently usable video and plots.
        self.workspace=tk.PanedWindow(self.window,orient='vertical',sashwidth=11,sashrelief='flat',
                                      showhandle=False,bg=C['line'],borderwidth=0,opaqueresize=True)
        self.workspace.pack(fill='both',expand=True,padx=18,pady=(0,8))
        video_box=tk.Frame(self.workspace,bg=C['panel'],highlightthickness=1,highlightbackground=C['line'])
        analysis_box=tk.Frame(self.workspace,bg=C['panel'],highlightthickness=1,highlightbackground=C['line'])
        self.workspace.add(video_box,minsize=180,height=220,stretch='always')
        self.workspace.add(analysis_box,minsize=270,height=470,stretch='always')
        self.window.after(260,self._set_initial_sash)

        video_head=tk.Frame(video_box,bg=C['panel']);video_head.pack(fill='x',padx=14,pady=(8,5))
        label(video_head,'02   BEFORE / AFTER VIDEO',weight='bold',size=12,fg=C['navy']).pack(side='left')
        ttk.Button(video_head,text='Enlarge analysis ↓',command=lambda:self.focus_panel('analysis')).pack(side='right')
        view=tk.Frame(video_box,bg=C['panel']);view.pack(fill='both',expand=True,padx=12)
        lframe=tk.Frame(view,bg=C['navy']);lframe.pack(side='left',fill='both',expand=True,padx=(0,5))
        rframe=tk.Frame(view,bg=C['navy']);rframe.pack(side='left',fill='both',expand=True,padx=(5,0))
        label(lframe,'ORIGINAL CAMERA VIDEO',weight='bold',size=10,fg='#d9eef5',bg=C['navy']).pack(fill='x',pady=(5,0))
        self.after_title = label(rframe,'AFTER PROCESSING',weight='bold',size=10,fg='#d9eef5',bg=C['navy'])
        self.after_title.pack(fill='x',pady=(5,0))
        self.left=ttk.Label(lframe,text='Select a video to begin',anchor='center',background=C['navy'],
                            foreground='white',font=('Segoe UI',12,'bold'))
        self.right=ttk.Label(rframe,text='No processed video yet',anchor='center',background=C['navy'],
                             foreground='white',font=('Segoe UI',12,'bold'))
        self.left.pack(fill='both',expand=True)
        self.right.pack(fill='both',expand=True)
        controls=tk.Frame(video_box,bg=C['panel']);controls.pack(fill='x',padx=12,pady=(5,7))
        self.play_btn=ttk.Button(controls,text='▶ Play',command=self.toggle_play,state='disabled')
        self.play_btn.pack(side='left',padx=(0,9))
        self.seek=ttk.Scale(controls,variable=self.seek_pos,from_=0,to=100,orient='horizontal')
        self.seek.pack(side='left',fill='x',expand=True,padx=6)
        self.seek.bind('<ButtonRelease-1>',self._seek_release)
        self.frame_text=label(controls,'0 / 0',size=10,bg=C['panel'])
        self.frame_text.pack(side='left',padx=10)
        ttk.Button(controls,text='Open results',command=self.open_output).pack(side='right')

        analysis_head=tk.Frame(analysis_box,bg=C['panel']);analysis_head.pack(fill='x',padx=14,pady=(7,2))
        label(analysis_head,'03   VERIFICATION & PERFORMANCE',size=12,weight='bold',fg=C['navy']).pack(side='left')
        ttk.Button(analysis_head,text='Expand charts ↗',command=self.open_analysis_window).pack(side='right',padx=(5,0))
        ttk.Button(analysis_head,text='Enlarge video ↑',command=lambda:self.focus_panel('video')).pack(side='right')

        metricrow=tk.Frame(analysis_box,bg=C['panel']);metricrow.pack(fill='x',padx=13,pady=(4,2))
        for title,var in [('X MOTION REDUCTION',self.stat_x),('Y MOTION REDUCTION',self.stat_y),('ROLL REDUCTION',self.stat_roll),
                          ('VIDEO FRAMES',self.stat_frames),('PROCESSING DURATION',self.stat_run)]:
            tile=tk.Frame(metricrow,bg=C['pale'],highlightthickness=1,highlightbackground='#dcebf0')
            tile.pack(side='left',fill='x',expand=True,padx=3)
            label(tile,title,size=9,weight='bold',fg=C['muted'],bg=C['pale']).pack(anchor='w',padx=13,pady=(5,0))
            tk.Label(tile,textvariable=var,font=('Segoe UI',18,'bold'),fg=C['teal'],bg=C['pale'],anchor='w').pack(anchor='w',padx=13,pady=(0,3))
        statusframe=tk.Frame(analysis_box,bg=C['panel']);statusframe.pack(fill='x',padx=17,pady=(1,2))
        tk.Label(statusframe,textvariable=self.validation,font=('Segoe UI',10,'bold'),fg=C['navy'],bg=C['panel'],anchor='w').pack(fill='x')
        tk.Label(statusframe,textvariable=self.image_metric,font=('Segoe UI',10),fg=C['muted'],bg=C['panel'],anchor='w').pack(fill='x')

        self.notebook=ttk.Notebook(analysis_box)
        self.notebook.pack(fill='both',expand=True,padx=10,pady=(2,9))
        charttab=ttk.Frame(self.notebook)
        spectab=ttk.Frame(self.notebook)
        imgtab=ttk.Frame(self.notebook)
        logtab=ttk.Frame(self.notebook)
        self.notebook.add(charttab,text='Motion curves')
        self.notebook.add(spectab,text='Frequency analysis')
        self.notebook.add(imgtab,text='Image stability')
        self.notebook.add(logtab,text='Evidence / logs')
        self.chartfig=Figure(figsize=(12,4),dpi=110,facecolor='#ffffff')
        self.chartax=self.chartfig.add_subplot(111)
        self.chartcanvas=FigureCanvasTkAgg(self.chartfig,master=charttab)
        axisrow=ttk.Frame(charttab);axisrow.pack(fill='x',pady=(3,0))
        ttk.Label(axisrow,text='Motion axis:').pack(side='left',padx=(10,5))
        for v in ('X','Y','ROLL'):
            ttk.Radiobutton(axisrow,text=v,variable=self.axis,value=v,command=self.draw_plots).pack(side='left',padx=9)
        self.chartcanvas.get_tk_widget().pack(fill='both',expand=True,padx=4)
        self.specfig=Figure(figsize=(12,4),dpi=110,facecolor='#ffffff')
        self.specax=self.specfig.add_subplot(111)
        self.speccanvas=FigureCanvasTkAgg(self.specfig,master=spectab)
        self.speccanvas.get_tk_widget().pack(fill='both',expand=True,padx=4,pady=3)
        self.imgfig=Figure(figsize=(12,4),dpi=110,facecolor='#ffffff')
        self.imgax=self.imgfig.add_subplot(111)
        self.imgcanvas=FigureCanvasTkAgg(self.imgfig,master=imgtab)
        self.imgcanvas.get_tk_widget().pack(fill='both',expand=True,padx=4,pady=3)
        self.log=scrolledtext.ScrolledText(logtab,height=7,wrap='word',font=('Consolas',11),
                                           bg='#f8fbfd',fg=C['text'],relief='flat',padx=15,pady=12)
        self.log.pack(fill='both',expand=True,padx=6,pady=5)
        self.log.configure(state='disabled')
        self.draw_image_metric();self.draw_plots()

        foot=tk.Frame(self.window,bg=C['navy'],height=30)
        foot.pack(fill='x');foot.pack_propagate(False)
        tk.Label(foot,textvariable=self.status,anchor='w',font=('Segoe UI',10),fg='#e5f1f6',
                 bg=C['navy']).pack(fill='both',padx=18)

        m=tk.Menu(self.window,font=('Segoe UI',11))
        file=tk.Menu(m,tearoff=False,font=('Segoe UI',11))
        file.add_command(label='Open video…',command=self.choose_video)
        file.add_command(label='Import naturally shaky footage…',command=self.real_footage_dialog)
        file.add_command(label='Load lab trajectory CSV…',command=self.choose_csv)
        file.add_command(label='Generate synthetic test clip',command=self.make_demo)
        file.add_separator();file.add_command(label='Exit',command=self._close)
        m.add_cascade(label='File',menu=file)
        hw=tk.Menu(m,tearoff=False,font=('Segoe UI',11))
        hw.add_command(label='Detect COM ports',command=self.refresh_ports)
        hw.add_command(label='Verify physical FPGA',command=self.hardware_test)
        hw.add_command(label='Process on hardware',command=lambda:self.process(True))
        hw.add_command(label='Software preview (not hardware evidence)',command=lambda:self.process(False))
        m.add_cascade(label='Hardware',menu=hw)
        viewmenu=tk.Menu(m,tearoff=False,font=('Segoe UI',11))
        viewmenu.add_command(label='Expand analysis charts',command=self.open_analysis_window)
        viewmenu.add_command(label='Focus analysis panel',command=lambda:self.focus_panel('analysis'))
        viewmenu.add_command(label='Focus video panel',command=lambda:self.focus_panel('video'))
        m.add_cascade(label='View',menu=viewmenu)
        helpmenu=tk.Menu(m,tearoff=False,font=('Segoe UI',11))
        helpmenu.add_command(label='Operator guide / F1',command=self.show_help)
        helpmenu.add_command(label='Program FPGA in Vivado',command=lambda:self.show_help('Program Arty A7'))
        m.add_cascade(label='Help',menu=helpmenu)
        self.window.configure(menu=m)
        self.window.bind('<Control-o>',lambda e:self.choose_video())

    def _set_initial_sash(self):
        """Reserve roughly half the workspace for meaningful analytical figures."""
        try:
            height=self.workspace.winfo_height()
            if height>480:
                self.workspace.sash_place(0,0,max(190,int(height*0.33)))
        except tk.TclError:
            pass

    def focus_panel(self,which):
        """One-click alternative to dragging the divider."""
        try:
            h=self.workspace.winfo_height()
            if h>450:
                self.workspace.sash_place(0,0,int(h*(.29 if which=='analysis' else .66)))
        except tk.TclError:pass

    def open_analysis_window(self):
        """Standalone high-resolution engineering dashboard with three real plots."""
        if self._analysis_window is not None:
            try:
                if self._analysis_window.winfo_exists():
                    self._analysis_window.lift();self._analysis_window.focus_force();return
            except tk.TclError:pass
        w=tk.Toplevel(self.window)
        self._analysis_window=w
        w.title('Maritime FPGA DSP  |  Expanded engineering analysis')
        w.geometry('1320x880');w.minsize(950,640)
        w.configure(bg='#edf3f8')
        header=tk.Frame(w,bg='#122e45');header.pack(fill='x')
        tk.Label(header,text='ENGINEERING ANALYSIS  /  CAMERA MOTION',font=('Segoe UI',16,'bold'),
                 fg='white',bg='#122e45').pack(side='left',padx=20,pady=16)
        panel=tk.Frame(w,bg='white');panel.pack(fill='both',expand=True,padx=16,pady=12)
        fig=Figure(figsize=(12,7),dpi=110,facecolor='white')
        a,b,c=fig.subplots(2,2).flatten()[:3]
        d=fig.axes[-1];d.set_axis_off()
        if self.result is None:
            for ax in (a,b,c):
                ax.text(.5,.5,'Load and process a video to view results',ha='center',va='center',transform=ax.transAxes)
                ax.set_axis_off()
            d.text(.08,.6,'Hardware status',fontsize=16,fontweight='bold')
            d.text(.08,.4,'No current video-processing result',fontsize=12)
        else:
            x,y=inputs_from_csv(self.result.trajectory)
            a_raw=np.array(x,dtype=float)/256; a_fil=np.array(self.result.filtered_trajectory['x'],dtype=float)/256
            b_raw=np.array(y,dtype=float)/256; b_fil=np.array(self.result.filtered_trajectory['y'],dtype=float)/256
            t=np.arange(len(a_raw))/30
            for ax,raw,fil,name in ((a,a_raw,a_fil,'Horizontal X'),(b,b_raw,b_fil,'Vertical Y')):
                ax.plot(t,raw,label='Original motion',color='#547e9a',alpha=.85)
                ax.plot(t,fil,label='FPGA-filtered' if self.result.metrics.get('hardware_verified') else 'Software-filtered',color='#00869e',linewidth=2)
                ax.set(xlabel='Time (s)',ylabel='Displacement (px)',title=name+' camera trajectory')
                ax.grid(alpha=.2);ax.legend(fontsize=9)
            def spectrum(v):
                v=v-np.mean(v)
                return 20*np.log10(np.maximum(1e-8,np.abs(np.fft.rfft(v)))/len(v))
            freq=np.fft.rfftfreq(len(a_raw),d=1/30.0)
            c.plot(freq,spectrum(a_raw),label='Original',color='#547e9a')
            c.plot(freq,spectrum(a_fil),label='Filtered',color='#00869e')
            c.set(xlabel='Frequency (Hz)',ylabel='Relative magnitude (dB)',title='Horizontal motion spectrum')
            c.grid(alpha=.2);c.legend(fontsize=9)
            m=self.result.metrics
            mode='PHYSICAL FPGA — BIT-EXACT' if m.get('hardware_verified') else 'SOFTWARE REFERENCE ONLY'
            d.text(.03,.89,mode,fontsize=11,fontweight='bold',color='#007b91',va='top')
            d.text(.03,.71,f"X reduction: {m['x']['reduction_pct']:.1f}%\nY reduction: {m['y']['reduction_pct']:.1f}%\nRoll reduction: {m.get('theta',{}).get('reduction_pct',float('nan')):.1f}%\nCrop retained: {m.get('crop',{}).get('area_retained_pct','N/A')}%\nProfile: {m.get('profile','Legacy')}\nFrames: {m['frames']}\nDuration: {self.result.elapsed_s:.2f} s",fontsize=10.5,linespacing=1.35,va='top')
            q=m.get('image_stability',{})
            d.text(.03,.14,('Image stability: '+str(q.get('status','Not evaluated'))),fontsize=11,va='top')
        fig.subplots_adjust(left=.07,right=.97,bottom=.09,top=.93,wspace=.27,hspace=.36)
        canvas=FigureCanvasTkAgg(fig,master=panel)
        canvas.get_tk_widget().pack(fill='both',expand=True)
        canvas.draw_idle()
        bottom=tk.Frame(w,bg='#edf3f8');bottom.pack(fill='x',padx=20,pady=(0,12))
        ttk.Button(bottom,text='Close dashboard',command=w.destroy).pack(side='right')
        self._analysis_fig=fig
        self._analysis_canvas=canvas

    def show_help(self, tab: str | None = None):
        self._help_window=open_help(self.window,self._help_window)
        if tab:
            tabs=self._help_window.winfo_children()[0].winfo_children()
            # locate TNotebook without relying on its widget path
            for child in tabs:
                if isinstance(child,ttk.Notebook):
                    for name in child.tabs():
                        if child.tab(name,'text')==tab:
                            child.select(name);break

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
        self.status.set('Video loaded. Choose PHYSICAL FPGA or software preview.')
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
                    self.status.set('Processing failed. Check Evidence and log tab.')
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

    def _open_pair_video(self,path):
        self._release_video()
        self.capture=cv2.VideoCapture(str(path))
        if not self.capture.isOpened():
            messagebox.showerror('Preview','Could not open generated comparison MP4. Check output folder.');return
        self.frames=int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps=float(self.capture.get(cv2.CAP_PROP_FPS) or 30)
        self.seek.configure(to=max(0,self.frames-1))
        self.play_btn.configure(state='normal')
        self._show_frame(0)

    def _show_source_frame(self):
        self._release_video()
        if not self.source:return
        cap=cv2.VideoCapture(str(self.source))
        ok,frame=cap.read();cap.release()
        if ok:
            self._render_label(self.left,frame,'left')
            self.right.configure(image='',text='STABILISED VIDEO\n\nProcess the selected video on the FPGA')

    def _render_label(self,label,frame,which):
        if frame is None:return
        ih,iw=frame.shape[:2]
        maxw=max(320,label.winfo_width()-8)
        maxh=max(150,label.winfo_height()-8)
        scale=min(maxw/max(1,iw),maxh/max(1,ih),1.7)
        sw,sh=max(1,int(iw*scale)),max(1,int(ih*scale))
        if sw != iw or sh != ih:frame=cv2.resize(frame,(sw,sh),interpolation=cv2.INTER_AREA)
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        img=ImageTk.PhotoImage(Image.fromarray(rgb))
        label.configure(image=img,text='')
        if which=='left':self._img_left=img
        else:self._img_right=img

    def _show_frame(self,index):
        if not self.capture:return
        index=int(max(0,min(self.frames-1,index)))
        self.capture.set(cv2.CAP_PROP_POS_FRAMES,index)
        ok,frame=self.capture.read()
        if not ok:return
        w=frame.shape[1]//2
        self._render_label(self.left,frame[:,:w],'left')
        self._render_label(self.right,frame[:,w:],'right')
        self.frame_idx=index
        self.seek_pos.set(index)
        self.frame_text.configure(text=f'{index+1} / {self.frames}')

    def toggle_play(self):
        if not self.capture:return
        self.playing=not self.playing
        self.play_btn.configure(text='❚❚ Pause' if self.playing else '▶ Play')
        if self.playing:self._play_tick()

    def _play_tick(self):
        if not self.playing:return
        next_frame=self.frame_idx+1
        if next_frame>=self.frames:
            self.playing=False
            self.play_btn.configure(text='▶ Play')
            return
        self._show_frame(next_frame)
        self.window.after(max(15,int(1000/self.fps)),self._play_tick)

    def _seek_release(self,event=None):
        if self.capture:self._show_frame(round(self.seek_pos.get()))

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

    def _release_video(self):
        self.playing=False
        if self.capture:self.capture.release();self.capture=None
        self.frames=0;self.frame_idx=0
        if hasattr(self,'play_btn'):
            self.play_btn.configure(text='▶ Play')
            self.seek_pos.set(0)

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
