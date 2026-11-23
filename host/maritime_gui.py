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
import time
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
from unified_pipeline import run_unified_pipeline
from audio_preservation import source_has_audio
from gui_audio_playback import SoundtrackPlayer
from generate_synthetic_clip import generate
from fixed_point_golden import FirReference
from fpga_serial_client import run_batch
from stabilize_video import inputs_from_csv
from affine_stabilization import read_path
from prepare_natural_footage import prepare_natural_footage, probe_raw
from engineering_summary import collect as collect_engineering_summary, to_markdown as engineering_to_markdown
from processing_control import ProcessingCancelled
from profile_comparison import compare_profiles


class MaritimeGUI:
    def __init__(self, window: tk.Tk):
        self.window = window
        self.window.title('Maritime FPGA DSP | Video Stabilisation & Audio Filtering')
        self.window.geometry('1440x850')
        self.window.minsize(1150,690)
        self.window.configure(bg='#edf3f8')
        self.events: queue.Queue = queue.Queue()
        self._help_window = None
        self._footage_window = None
        self._analysis_window = None
        self._audio_window = None
        self._filter_window = None
        self.source: Path | None = None
        self.trajectory: Path | None = None
        self.result = None
        self.capture = None
        # One player handles either a raw input (left panel only) or a
        # processed side-by-side MP4. Timers are cancelled on pause/reload.
        self._playback_kind = None  # 'source' or 'pair'
        self._play_after_id = None
        self._play_start = 0.0
        self._play_start_frame = 0
        self.soundtrack = SoundtrackPlayer()
        self.audio_choice = tk.StringVar(value='Original')
        self.frames = 0
        self.frame_idx = 0
        self.fps = 30.0
        self.playing = False
        self.busy = False
        self._cancel_event = None
        self._job_is_processing = False
        self._job_has_audio = False
        self._job_is_comparison = False
        self._job_started = 0.0
        self._last_progress_emit = 0.0
        self.progress_label = tk.StringVar(value='Ready for processing')
        self.progress_pct = tk.DoubleVar(value=0.0)
        self._seek_enabled = True
        self._img_left = None
        self._img_right = None
        self.comport = tk.StringVar(value='')
        self.video_info = tk.StringVar(value='No video selected')
        self.assessment_context = tk.StringVar(value='Source: none  |  Video assessment: not run')
        self.audio_context = tk.StringVar(value='Source: none  |  Audio assessment: not run')
        self.audio_stage = tk.StringVar(value='Audio FIR: not run')
        self.audio_high = tk.StringVar(value='—')
        self.audio_mid = tk.StringVar(value='—')
        self.audio_rumble = tk.StringVar(value='—')
        self.audio_cleanup_mode = tk.StringVar(value='Maritime adaptive')
        self.motion_mode = tk.StringVar(value='Natural footage: automatic OpenCV motion estimation (no CSV or synthetic shake)')
        self.input_kind = 'NATURAL'
        self.image_metric = tk.StringVar(value='Independent image stability: not assessed')
        self.profile_comparison_text = tk.StringVar(value='Compare Normal and Strong using a software-reference test; neither result is FPGA evidence.')
        self.profile_comparison_file = None
        self.validation = tk.StringVar(value='No hardware verification yet')
        self.status = tk.StringVar(value='Ready. Choose a video or generate the example clip.')
        self.stat_x = tk.StringVar(value='—')
        self.stat_y = tk.StringVar(value='—')
        self.stat_roll = tk.StringVar(value='—')
        self.profile = tk.StringVar(value='Normal')
        self.processing_mode = tk.StringVar(value='Video only')
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
        """Five-tab UI: implementation, video assessment, audio assessment, summary report, help.

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
        tk.Label(header,text='MARITIME  /  VIDEO + AUDIO DSP',
                 font=('Segoe UI',15,'bold'),bg=C['navy'],fg='#f7fbfd').pack(side='left',padx=18)
        tk.Label(header,text='ARTY A7   •   CAMERA + SPEECH FIR',
                 font=('Segoe UI',9),bg=C['navy'],fg='#bed3de').pack(side='right',padx=18)

        self.main_tabs=ttk.Notebook(self.window)
        self.main_tabs.pack(fill='both',expand=True,padx=9,pady=(6,4))
        self.implementation_tab=ttk.Frame(self.main_tabs)
        self.assessment_tab=ttk.Frame(self.main_tabs)  # compatibility alias: Video Assessment
        self.audio_assessment_tab=ttk.Frame(self.main_tabs)
        self.summary_tab=ttk.Frame(self.main_tabs)
        self.help_tab=ttk.Frame(self.main_tabs)
        self.main_tabs.add(self.implementation_tab,text='Implementation')
        self.main_tabs.add(self.assessment_tab,text='Video Assessment')
        self.main_tabs.add(self.audio_assessment_tab,text='Audio Assessment')
        self.main_tabs.add(self.summary_tab,text='Summary Report')
        self.main_tabs.add(self.help_tab,text='Help')

        # All primary actions sit on ONE toolbar row. Specialised lab features
        # are kept accessible in File, not crowding out the video.
        toolbar=ttk.Frame(self.implementation_tab)
        toolbar.pack(side='top',fill='x',padx=9,pady=(9,7))
        self.open_btn=ttk.Button(toolbar,text='Open video',command=self.choose_video)
        self.open_btn.pack(side='left',padx=(0,4))
        ttk.Button(toolbar,text='Reset',command=self.reset_view).pack(side='left',padx=(0,4))
        ttk.Label(toolbar,text='Mode').pack(side='left',padx=(1,2))
        self.processing_combo=ttk.Combobox(toolbar,textvariable=self.processing_mode,
                                          values=('Video + Audio','Video only'),state='readonly',width=13)
        self.processing_combo.pack(side='left',padx=(0,5))
        self.sw_btn=ttk.Button(toolbar,text='Software preview',command=lambda:self.process(False))
        self.sw_btn.pack(side='left',padx=(0,6))
        ttk.Label(toolbar,text='COM').pack(side='left',padx=(0,4))
        self.port_entry=ttk.Combobox(toolbar,textvariable=self.comport,width=7,state='normal')
        self.port_entry.pack(side='left',padx=(0,4))
        ttk.Button(toolbar,text='Ports',command=self.refresh_ports).pack(side='left',padx=(0,4))
        self.test_btn=ttk.Button(toolbar,text='Verify FPGA',command=self.hardware_test)
        self.test_btn.pack(side='left',padx=(0,10))
        self.hw_btn=ttk.Button(toolbar,text='Process on FPGA',style='Accent.TButton',
                               command=lambda:self.process(True))
        self.hw_btn.pack(side='left',padx=(0,4))
        ttk.Label(toolbar,text='Smoothing').pack(side='left',padx=(0,4))
        self.profile_combo=ttk.Combobox(toolbar,textvariable=self.profile,
                                        values=['Normal','Strong'],state='readonly',width=8)
        self.profile_combo.pack(side='left')
        # Advanced import/lab functions are collected under Tools below.
        self.demo_btn=ttk.Button(self.implementation_tab,text='Synthetic test',command=self.make_demo)
        self.csv_btn=ttk.Button(self.implementation_tab,text='Lab trajectory',command=self.choose_csv)
        self.real_btn=ttk.Button(self.implementation_tab,text='Prepare recording',command=self.real_footage_dialog)

        # A single, small input-information line. Avoid displaying lengthy
        # processing descriptions on top of the video or in large type.
        info=tk.Frame(self.implementation_tab,bg=C['panel'])
        info.pack(fill='x',padx=9,pady=(0,6))
        # A single on-screen location for audio-cleanup selection; it was
        # previously hidden in File, where it did not belong.
        self.tools_menu=tk.Menu(self.window,tearoff=False,font=('Segoe UI',9))
        self.tools_menu.add_command(label='Prepare natural recording…',command=self.real_footage_dialog)
        self.tools_menu.add_command(label='Generate synthetic test clip',command=self.make_demo)
        self.tools_menu.add_command(label='Import lab trajectory CSV…',command=self.choose_csv)
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label='Open audio FIR lab…',command=self.open_audio_dialog)
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label='How to measure FPGA die temperature (XADC)',
                                    command=lambda:self.show_help('FPGA die temperature using XADC'))
        self.tools_button=ttk.Menubutton(info,text='Tools ▾',direction='below',menu=self.tools_menu)
        self.tools_button.pack(side='right',padx=(6,6),pady=2)
        self.cleanup_combo=ttk.Combobox(info,textvariable=self.audio_cleanup_mode,
                values=('Maritime adaptive','FIR only'),state='readonly',width=17)
        self.cleanup_combo.pack(side='right',padx=(0,4),pady=2)
        ttk.Label(info,text='Audio cleanup:').pack(side='right',padx=(8,4))
        tk.Label(info,textvariable=self.video_info,font=('Segoe UI',9),bg=C['panel'],
                 fg=C['muted'],anchor='w').pack(side='left',fill='x',expand=True,padx=9,pady=3)
        self.motion_mode_label = None  # Details are in the Help tab and evidence.

        # A single compact status/progress strip. The percentage is workflow
        # progress, not a prediction of UART completion time.
        progress_frame=ttk.Frame(self.implementation_tab)
        progress_frame.pack(side='top',fill='x',padx=9,pady=(0,5))
        ttk.Label(progress_frame,textvariable=self.progress_label,width=48,anchor='w').pack(side='left',padx=(2,8))
        self.progressbar=ttk.Progressbar(progress_frame,variable=self.progress_pct,
                                         maximum=100,mode='determinate')
        self.progressbar.pack(side='left',fill='x',expand=True,padx=(0,6))
        self.cancel_btn=ttk.Button(progress_frame,text='Cancel processing',
                                   command=self.request_cancel,state='disabled')
        self.cancel_btn.pack(side='left')

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
        self.play_btn.pack(side='left',padx=(0,7))
        ttk.Label(playback,text='Audio').pack(side='left',padx=(0,4))
        self.audio_combo=ttk.Combobox(playback,textvariable=self.audio_choice,
                                      values=('Original','Filtered','Mute'),
                                      width=9,state='readonly')
        self.audio_combo.pack(side='left',padx=(0,10))
        self.audio_combo.bind('<<ComboboxSelected>>',self._change_audio_choice)
        self.seek=ttk.Scale(playback,variable=self.seek_pos,from_=0,to=100,orient='horizontal')
        self.seek.pack(side='left',fill='x',expand=True,padx=4)
        self.seek.bind('<ButtonPress-1>',self._seek_press)
        self.seek.bind('<ButtonRelease-1>',self._seek_release)
        self.frame_text=ttk.Label(playback,text='0 / 0',width=11)
        self.frame_text.pack(side='left',padx=(12,5))
        ttk.Button(playback,text='Results folder',command=self.open_output).pack(side='right',padx=(8,0))
        ttk.Button(playback,text='Play MP4 with audio',command=self.open_media_with_audio).pack(side='right',padx=(8,0))

        # Assessment tab: large plotting region, all verification data together.
        assess_top=ttk.Frame(self.assessment_tab)
        assess_top.pack(fill='x',padx=12,pady=(8,5))
        tk.Label(assess_top,textvariable=self.assessment_context,anchor='w',
                 font=('Segoe UI',10,'bold'),fg=C['navy'],bg=C['panel']).pack(fill='x',padx=6,pady=(0,8))
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
        profile_row=ttk.Frame(assess_top)
        profile_row.pack(fill='x',padx=6,pady=(2,4))
        self.compare_btn=ttk.Button(profile_row,text='Compare Normal / Strong',command=self.compare_smoothing)
        self.compare_btn.pack(side='left',padx=(0,8))
        ttk.Label(profile_row,textvariable=self.profile_comparison_text).pack(side='left',fill='x',expand=True)

        # Small view controls; the selected plot fills the remaining tab height.
        plotbar=ttk.Frame(self.assessment_tab)
        plotbar.pack(fill='x',padx=14,pady=(3,4))
        self.assess_view=tk.StringVar(value='Motion curves')
        for title in ('Motion curves','Frequency spectrum','Image stability','Profile comparison','Evidence log'):
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
            elif name=='Image stability':
                self.imgfig,self.imgax,self.imgcanvas=fig,ax,canvas
        self.log=scrolledtext.ScrolledText(self.assessment_content,wrap='word',
                                           font=('Consolas',10),bg='#f8fafc',
                                           fg=C['text'],relief='flat',padx=12,pady=12)
        self.log.configure(state='disabled')
        self._assess_widgets['Evidence log']=self.log
        # Full precision comparison table, distinct from the compact status text.
        # Initially show the explicitly labelled archived SOFTWARE reference,
        # then replace it with the current video's comparison when run.
        profile_panel=ttk.Frame(self.assessment_content)
        self.profile_source_label=tk.StringVar(value='No profile comparison loaded')
        self.profile_provenance_label=tk.StringVar(value='SOFTWARE REFERENCE ONLY — no physical FPGA processing')
        self.profile_interpretation=tk.StringVar(value='Independent image-content registration must be inspected separately.')
        ttk.Label(profile_panel,text='Normal versus Strong — camera-motion assessment',
                  font=('Segoe UI',15,'bold')).pack(anchor='w',padx=12,pady=(14,5))
        ttk.Label(profile_panel,textvariable=self.profile_source_label).pack(anchor='w',padx=12,pady=(0,4))
        ttk.Label(profile_panel,textvariable=self.profile_provenance_label,
                  font=('Segoe UI',10,'bold'),foreground='#a65b16').pack(anchor='w',padx=12,pady=(0,10))
        table_wrap=ttk.Frame(profile_panel)
        table_wrap.pack(fill='x',padx=12)
        self.profile_comparison_table=ttk.Treeview(table_wrap,columns=('metric','normal','strong'),
                                  show='headings',height=5,selectmode='browse')
        for key,title,width,anchor in (('metric','Measured characteristic',380,'w'),
                       ('normal','Normal',145,'center'),('strong','Strong',145,'center')):
            self.profile_comparison_table.heading(key,text=title)
            self.profile_comparison_table.column(key,width=width,minwidth=95,anchor=anchor,stretch=False)
        self.profile_comparison_table.pack(fill='x',expand=True)
        ttk.Label(profile_panel,textvariable=self.profile_interpretation,
                  wraplength=960,justify='left').pack(fill='x',padx=12,pady=(14,6))
        ttk.Label(profile_panel,text='High-frequency trajectory reduction is not proof of visible image-stability improvement. More smoothing can crop more of the source image.',
                  wraplength=960,justify='left').pack(fill='x',padx=12,pady=(2,8))
        self._assess_widgets['Profile comparison']=profile_panel
        ref=ROOT/'evidence/quality_2026-11-23_reference/normal_strong_reference.json'
        if ref.exists():
            try:self._update_profile_comparison(json.loads(ref.read_text(encoding='utf-8')),label='ARCHIVED 3-second SOFTWARE-REFERENCE result')
            except (ValueError,KeyError,OSError):pass
        self._show_assessment_view()

        # Audio has its own full-height assessment workspace: no competing
        # camera-motion charts or miniature plots in this tab.
        audio_top=ttk.Frame(self.audio_assessment_tab)
        audio_top.pack(fill='x',padx=14,pady=(10,8))
        tk.Label(audio_top,textvariable=self.audio_context,anchor='w',
                 font=('Segoe UI',10,'bold'),fg=C['navy'],bg=C['panel']).pack(fill='x',padx=6,pady=(0,6))
        tk.Label(audio_top,textvariable=self.audio_stage,anchor='w',
                 font=('Segoe UI',9),fg=C['muted'],bg=C['panel']).pack(fill='x',padx=6,pady=(0,7))
        audio_tiles=ttk.Frame(audio_top);audio_tiles.pack(fill='x')
        for label,value in [('40–180 Hz rumble',self.audio_rumble),
                            ('5–7.5 kHz band change',self.audio_high),
                            ('250–3000 Hz band change',self.audio_mid)]:
            tile=tk.Frame(audio_tiles,bg=C['pale']);tile.pack(side='left',fill='x',expand=True,padx=3)
            tk.Label(tile,text=label,font=('Segoe UI',9),bg=C['pale'],fg=C['muted']).pack(anchor='w',padx=12,pady=(7,0))
            tk.Label(tile,textvariable=value,font=('Segoe UI',16,'bold'),bg=C['pale'],fg=C['navy']).pack(anchor='w',padx=12,pady=(0,7))
        tk.Label(audio_top,text='Spectral-band changes are not proof of voice clarity or isolated-noise removal.',
                 font=('Segoe UI',9),fg=C['muted'],bg=C['panel']).pack(anchor='w',padx=8,pady=(7,2))
        self.audiofig=Figure(figsize=(12,6),dpi=110,facecolor='#ffffff')
        self.audioax=self.audiofig.add_subplot(111)
        self.audiocanvas=FigureCanvasTkAgg(self.audiofig,master=self.audio_assessment_tab)
        self.audiocanvas.get_tk_widget().pack(fill='both',expand=True,padx=14,pady=(0,12))

        # Summary Report is a read-only view of explicit provenance-linked results.
        # It does not run a build, create test passes or pretend to measure hardware.
        summary_header=ttk.Frame(self.summary_tab)
        summary_header.pack(fill='x',padx=15,pady=(13,8))
        ttk.Label(summary_header,text='FPGA ENGINEERING SUMMARY',font=('Segoe UI',13,'bold')).pack(side='left',padx=(0,16))
        ttk.Button(summary_header,text='Refresh evidence',command=self.refresh_summary_report).pack(side='right',padx=4)
        ttk.Button(summary_header,text='FIR design curves',command=self.show_filter_curves).pack(side='right',padx=4)
        ttk.Button(summary_header,text='Quality charts',command=self.show_quality_figures).pack(side='right',padx=4)
        ttk.Button(summary_header,text='Test commands',command=lambda:self.show_help('Testing & commands')).pack(side='right',padx=4)
        ttk.Button(summary_header,text='Export report',command=self.export_summary_report).pack(side='right',padx=4)
        self.summary_origin=tk.StringVar(value='Evidence source: checking local archive')
        tk.Label(self.summary_tab,textvariable=self.summary_origin,anchor='w',
                 font=('Segoe UI',9),fg=C['muted'],bg=C['panel']).pack(fill='x',padx=19,pady=(0,7))
        summary_cards=ttk.Frame(self.summary_tab)
        summary_cards.pack(fill='x',padx=14,pady=(0,12))
        self.summary_tiles={}
        for label in ('Clock','Setup slack','LUTs','FPGA power (est.)','Die temp (XADC)','Reliability'):
            tile=tk.Frame(summary_cards,bg=C['pale'])
            tile.pack(side='left',fill='x',expand=True,padx=3)
            tk.Label(tile,text=label,font=('Segoe UI',9),bg=C['pale'],fg=C['muted']).pack(anchor='w',padx=10,pady=(8,1))
            state=tk.StringVar(value='—')
            tk.Label(tile,textvariable=state,font=('Segoe UI',13,'bold'),bg=C['pale'],fg=C['navy']).pack(anchor='w',padx=10,pady=(0,9))
            self.summary_tiles[label]=state
        self.summary_text=scrolledtext.ScrolledText(self.summary_tab,wrap='word',
                   font=('Consolas',10),bg='#f8fafc',fg=C['text'],relief='flat',padx=15,pady=12)
        self.summary_text.pack(fill='both',expand=True,padx=17,pady=(0,14))
        self.summary_text.configure(state='disabled')
        self.summary_text.tag_configure('major',font=('Segoe UI',16,'bold'),foreground=C['navy'],spacing1=10,spacing3=10)
        self.summary_text.tag_configure('minor',font=('Segoe UI',12,'bold'),foreground=C['teal'],spacing1=13,spacing3=7)
        self.summary_text.tag_configure('note',foreground=C['muted'],spacing3=8)

        # Keep the five main tabs; organise detailed guidance inside Help only.
        self.help_subtabs=ttk.Notebook(self.help_tab)
        self.help_subtabs.pack(fill='both',expand=True,padx=14,pady=10)
        help_frame=tk.Frame(self.help_subtabs,bg=C['panel'])
        self.help_subtabs.add(help_frame,text='Operator guide')
        command_frame=ttk.Frame(self.help_subtabs)
        self.help_subtabs.add(command_frame,text='Testing & commands')
        self._build_command_guide(command_frame)
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
            '2. Open a video. Software preview needs no board. For FPGA mode select COM (previously COM4), then Verify FPGA.',
            '3. Use Open video for a prepared 30 fps video, or Tools → Prepare natural recording for unprepared footage.',
            '4. Choose Video + Audio for one stabilised MP4 with filtered soundtrack; Video only retains original sound.',
            '5. Play or replay with audio. Video Assessment shows motion and crop performance; Audio Assessment shows audio stages and spectrum.'
        ])
        add_section('Program the FPGA in Vivado',[
            'Connect the Arty A7 via USB, power the board and launch Vivado 2025.2.1.',
            'If you have no bitstream, rebuild from the project root:',
            r'  & "C:\AMDDesignTools\2025.2.1\Vivado\bin\vivado.bat" -mode batch -source hardware/vivado/build_maritime_bitstream.tcl',
            r'Open Hardware Manager → Open target → Auto Connect → Program Device.',
            r'Select hardware\build\maritime_a7.runs\impl_1\arty_a7_maritime_top.bit.',
            'After successful programming, select its USB-UART COM port. BTN0 resets the FPGA logic; Reset view resets only the GUI.'
        ])
        add_section('Implementation controls',[
            'Open video — load compatible 30-fps video from videos/ (18–1500 frames, up to 1280×720).',
            'Reset view — clear displayed results; does not program or reset the board.',
            'COM / Detect ports — choose the physical USB serial port and refresh the list.',
            'Verify FPGA checks 3 motion sequences plus the audio coefficient bank when Video + Audio is selected.',
            'Verify FPGA — send three reference cases and compare every returned result bit-for-bit.',
            'Stabilise using FPGA — estimate X/Y/roll on the PC, filter via the physical FPGA and warp frames on the PC.',
            'Software preview — run the same pipeline in Python, explicitly NOT hardware verification. This button is next to Reset view.',
            'Smoothing: Normal = one motion FIR pass per axis; Strong = two. Audio FIR runs once regardless of this setting.',
            'Processing: Video + Audio performs both DSP paths from one MP4. Video only retains its soundtrack.',
            'Strong is not automatically better: it can increase cropping and suppress intentional pans.',
            'The Tools control beside the video information provides natural-footage import, synthetic test clips and lab trajectories; none is needed for an ordinary video run.'
        ])
        add_section('Video and Audio Assessment',[
            'Motion curves — original vs filtered X, Y or roll trajectory over time.',
            'Frequency spectrum — compare attenuation across camera-motion frequencies.',
            'Image stability — independent image-content registration before vs after (can be INCONCLUSIVE).',
            'Video Assessment — motion curves, camera-motion frequency spectrum, image stability, evidence log.',
            'Audio Assessment — original vs FPGA FIR-only vs final adaptive audio spectrum, with truthful stage attribution.',
            'Each assessment tab reports the source filename and processing mode. Hardware bit-exact FIR verification is distinct from PC-only adaptive spectral cleanup.',
            'Evidence log — inspect bit-exact verification, output files, quality warnings and errors.',
            'Numeric FIR improvements do not prove visibly improved images. Look at the videos and independent measurement.'
        ])
        add_section('Reproducible tests and commands',[ 
            'Open Help → Testing & commands for the Windows PowerShell and Vivado Tcl procedures, grouped by verification level.',
            'The same commands are maintained in docs/TEST_AND_VERIFICATION_COMMANDS.md. Copy the relevant command block and check paths and COM port.',
            'Model plots, XSim, Vivado estimates, physical board reliability, image/audio measurements and XADC snapshots are distinct evidence classes.'
        ])
        add_section('Summary Report and engineering validation',[
            'Summary Report reads current local build reports where supplied, otherwise clearly labelled owner-uploaded RevD evidence and physical trial history; no new FPGA build is inferred.',
            'Refresh evidence loads a newer local evidence/final_validation build if present. Export report writes Markdown and JSON.',
            'After a native Vivado GUI implementation, run hardware/vivado/export_open_vivado_reports.tcl in the Vivado Tcl Console; then click Refresh evidence.',
            'To generate filter coefficient frequency-response plots and integer edge-case checks: python verification/model/industrial_filter_assessment.py.',
            'To run both self-checking XSim benches use hardware/sim/scripts/run_maritime_xsim.ps1 and hardware/sim/scripts/run_fir_xsim.ps1 with Vivado on PATH.',
            'Direct portable native Vivado .xpr: hardware/build/maritime_a7.xpr. Re-create a fresh project with OPEN_VIVADO_PROJECT_WINDOWS.ps1 -Recreate.',
            'Passing routed timing does NOT clear existing external I/O warnings or prove physical video/audio quality.',
        ])
        add_section('FPGA die temperature using XADC',[
            'Temperature has NOT been captured automatically. The 0.071 W figure is a Vivado vectorless power estimate, NOT a temperature or power measurement.',
            'Power the Arty A7 and open Vivado Hardware Manager → Open Target → Auto Connect. Program the verified bitstream if necessary.',
            'In the Vivado Tcl Console, change into the RevF project root (use forward slashes and your own extracted folder path):',
            r'  cd {C:/path/to/FPGA_Maritime_AV_RevF}',
            'Capture an actual idle die-temperature sample:',
            r'  set ::env(MARITIME_PHASE) idle',
            r'  source hardware/vivado/sample_xadc_snapshot.tcl',
            'Optionally capture another snapshot while or after running a real workload; set MARITIME_PHASE to during_workload or after_workload before sourcing again.',
            'The script saves evidence/final_validation/xadc_snapshots.csv. The archived 23 November 2026 readings are in evidence/xadc_2026-11-23 and will appear if no local readings exist. It reports die temperature only, not room temperature or board input watts.',
            'Close Vivado serial terminals before running UART tests. Hardware Manager may remain open for XADC, but do not open a serial console on COM4.',
            'In the Summary Report tab click Refresh evidence to display the measured XADC values. A missing CSV correctly remains NOT MEASURED.',
            'A snapshot taken after the earlier soak cannot retroactively establish its actual operating temperature. Compare readings only when conditions and timing are documented.'
        ])
        add_section('Project scope',[
            'The PC estimates camera motion and warps frames. The FPGA filters numeric X/Y/roll trajectories only.',
            'This is an offline 30 fps demonstration; no camera/video signal is streamed directly through the FPGA.',
            'Moving waves/ships, blur, limited background texture and perspective changes can reduce effectiveness.',
            'Sources live at videos/. Results are kept separately in videos/sim/ or videos/hrd/.\n            Videos up to 50 s are sent as overlapping FIR batches; no bitstream changes.\n            Video + Audio mode embeds the speech-band filtered soundtrack in a new final MP4; Video only retains original audio. The embedded Windows player supports synchronized audio and video. On other systems, Play MP4 with audio opens the comparison in the media player.\n            Use licensed, genuinely recorded shaky maritime footage for final industrial evidence.'
        ])
        add_section('Maritime background-noise reduction (v1.1)',[
            'Tools → Open audio FIR lab opens the offline WAV/MP4 audio-processing dialog.',
            'Choose a 2–4 second segment (maximum 30 seconds), then Software preview to compare original and speech-band filtered sound.',
            'Windows WAV Play buttons emit actual sound through your speakers. The embedded video frames remain silent.',
            'Two-stage audio: 16 kHz mono 17-tap FPGA FIR for hiss, then HOST spectral noise estimation from quieter frames and gentle low-frequency rumble reduction. Choose Audio cleanup on the Implementation tab: Maritime adaptive (default) or FIR only.',
            'The spectral enhancement runs on the PC, NOT the FPGA. It cannot guarantee removal of wind, sea noise or machinery that overlaps voice.',
            'Physical combined mode requires the NEW v0.9+ FPGA bitstream: high job-ID bit selects the audio bank. The old v0.8.2 bitstream is video only.',
            'The FPGA serial path is buffered and much slower than live audio. All hardware outputs must match the Python fixed-point reference bit-for-bit.',
            'Combined mode exports final_stabilised_filtered_audio.mp4, the two WAVs, A/B WAV and an audio spectrum in videos/sim/ or videos/hrd/.',
            'Audio processing is offline and may take much longer than video duration over the 115200-baud serial link.',
        ])
        self.help_text.configure(state='disabled')

        footer=tk.Frame(self.window,bg=C['navy'],height=27)
        footer.pack(side='bottom',fill='x');footer.pack_propagate(False)
        tk.Label(footer,textvariable=self.status,anchor='w',font=('Segoe UI',9),
                 fg='#e9f3f7',bg=C['navy']).pack(fill='both',padx=12)

        # Navigation is exclusively through the five notebook tabs.
        # No duplicate tabs or confusing processing settings in a File menu.
        self.window.bind('<Control-o>',lambda event:self.choose_video())
        self.draw_image_metric(); self.draw_plots(); self.draw_audio_metric(); self.refresh_summary_report()

    def refresh_summary_report(self):
        """Show only evidence already on disk, with archive/live classification."""
        metrics=self.result.metrics if self.result is not None else None
        summary=collect_engineering_summary(ROOT,metrics)
        self.summary_origin.set('Evidence: '+str(summary.get('report_provenance') or 'NOT AVAILABLE')+
                                ('  |  OWNER-UPLOADED/ARCHIVED REPORT' if summary.get('historical_baseline')
                                 else '  |  LATEST LOCAL BUILD'))
        t=summary.get('timing',{})
        r=summary.get('resources',{})
        def num(v,unit=''):
            return ('—' if v is None else str(v)+unit)
        self.summary_tiles['Clock'].set(num(summary.get('clock_mhz'),' MHz'))
        self.summary_tiles['Setup slack'].set(num(t.get('setup_wns_ns'),' ns'))
        self.summary_tiles['LUTs'].set(num(r.get('luts')))
        self.summary_tiles['FPGA power (est.)'].set(num(summary.get('estimated_power_w'),' W'))
        xadc=summary.get('xadc',{})
        self.summary_tiles['Die temp (XADC)'].set(num(xadc.get('latest_c'),'°C') if xadc.get('status')=='MEASURED' else 'Not measured')
        pc=summary.get('physical_campaign',{})
        self.summary_tiles['Reliability'].set('3/3 latest PASS*' if all(pc.get(x,{}).get('all_passed') for x in ('cold','reset','soak')) else 'Review evidence')
        md=engineering_to_markdown(summary)
        self._show_formatted_summary(md)
        self._summary_data=summary
        return summary

    def _show_formatted_summary(self, markdown):
        """Render an uncluttered, aligned report in Tk without external browser dependencies."""
        import re
        lines=markdown.splitlines()
        self.summary_text.configure(state='normal')
        self.summary_text.delete('1.0','end')
        i=0
        while i<len(lines):
            line=lines[i].strip()
            if line.startswith('## '):
                self.summary_text.insert('end',line[3:]+'\n','minor')
            elif line.startswith('# '):
                self.summary_text.insert('end',line[2:]+'\n','major')
            elif line.startswith('> '):
                self.summary_text.insert('end',line[2:]+'\n','note')
            elif line.startswith('|'):
                rows=[]
                while i<len(lines) and lines[i].strip().startswith('|'):
                    raw=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                    if not all(re.fullmatch(r'[-: ]+',cell) for cell in raw):
                        rows.append(raw)
                    i+=1
                if rows:
                    widths=[max(len(r[j]) if j<len(r) else 0 for r in rows) for j in range(max(map(len,rows)))]
                    for k,row in enumerate(rows):
                        entry='   '.join(v.ljust(widths[j]) for j,v in enumerate(row)).rstrip()
                        self.summary_text.insert('end',entry+'\n')
                        if k==0:self.summary_text.insert('end',('─'*min(len(entry),140))+'\n','note')
                continue
            elif line.startswith('- '):
                self.summary_text.insert('end','• '+re.sub(r'[`*]', '',line[2:])+'\n')
            else:
                self.summary_text.insert('end',re.sub(r'[`*]', '',line)+'\n')
            i+=1
        self.summary_text.configure(state='disabled')

    def show_filter_curves(self):
        """Numerical *coefficient* magnitude response, NEVER FPGA measurement."""
        if self._filter_window is not None and self._filter_window.winfo_exists():
            self._filter_window.lift();return
        from fixed_point_golden import load_coefficients
        from design_audio_coefficients import design
        win=tk.Toplevel(self.window)
        win.title('FIR coefficient frequency response — model only')
        win.geometry('980x680')
        self._filter_window=win
        top=ttk.Frame(win);top.pack(fill='x',padx=12,pady=(12,6))
        ttk.Label(top,text='Analytical coefficient frequency response (not FPGA measured)',
                  font=('Segoe UI',12,'bold')).pack(anchor='w')
        ttk.Label(top,text='Impulse/DC and bit-exact integer tests are recorded separately in Filter Reference Assessment.').pack(anchor='w')
        tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True,padx=12,pady=10)
        for name,coeff,fs in [('Camera-motion FIR',load_coefficients(),30.0),
                              ('16 kHz audio FIR',design(),16000.0)]:
            frame=ttk.Frame(tabs);tabs.add(frame,text=name)
            fig=Figure(figsize=(9,5),dpi=100)
            ax=fig.add_subplot(111)
            freqs=np.linspace(0,fs/2,1025)
            hh=np.exp(-2j*np.pi*freqs[:,None]*np.arange(len(coeff))[None,:]/fs) @ (np.asarray(coeff)/(2**15))
            db=20*np.log10(np.maximum(np.abs(hh),1e-14))
            ax.plot(freqs,db)
            ax.axhline(-3.0103,linestyle='--',linewidth=1,label='-3 dB reference')
            ax.set(xlabel='Frequency (Hz)',ylabel='Magnitude (dB)',ylim=(-120,5),
                   title=f'{name} | 17 taps | Q1.15 | coefficient model')
            ax.grid(alpha=.25);ax.legend(loc='lower left')
            fig.tight_layout()
            canvas=FigureCanvasTkAgg(fig,master=frame)
            canvas.draw();canvas.get_tk_widget().pack(fill='both',expand=True)

    def show_quality_figures(self):
        """Show labelled software-only sample assessment plots, not physical measurements."""
        paths=[('Audio spectral-band response',ROOT/'docs/figures/2026-11-23_audio_stage_band_changes_SOFTWARE.png'),
               ('Video trajectory reduction',ROOT/'docs/figures/2026-11-23_trajectory_reduction_SOFTWARE.png')]
        from PIL import Image, ImageTk
        win=tk.Toplevel(self.window);win.title('Media performance proxy — 3-second SOFTWARE REFERENCE ONLY')
        win.geometry('1050x690')
        ttk.Label(win,text='3-second sample: software FIR/host processing; independent image stability inconclusive',
                  font=('Segoe UI',11,'bold')).pack(anchor='w',padx=15,pady=12)
        tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True,padx=14,pady=(0,16))
        retained=[]
        for name,path in paths:
            frame=ttk.Frame(tabs);tabs.add(frame,text=name)
            if not path.is_file():
                ttk.Label(frame,text='Plot not shipped; run verification/system/media_quality_assessment.py').pack(padx=20,pady=20)
                continue
            img=Image.open(path).convert('RGB')
            img.thumbnail((980,565))
            tkimg=ImageTk.PhotoImage(img,master=win)
            retained.append(tkimg)
            tk.Label(frame,image=tkimg).pack(expand=True)
        win._quality_images=retained

    def export_summary_report(self):
        from tkinter import filedialog
        path=filedialog.asksaveasfilename(title='Export engineering summary',
                   initialfile='maritime_engineering_summary.md',defaultextension='.md',
                   filetypes=[('Markdown report','*.md')])
        if not path:return
        destination=Path(path)
        try:
            data=self.refresh_summary_report()
            destination.write_text(engineering_to_markdown(data),encoding='utf-8')
            destination.with_suffix('.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
            self.status.set('Engineering report exported: '+str(destination))
        except OSError as e:messagebox.showerror('Report export failed',str(e))

    def _build_command_guide(self,parent):
        # Markdown file is authoritative; the GUI reads it rather than
        # maintaining a second drifting copy of Windows/Vivado commands.
        guide=ROOT/'docs/TEST_AND_VERIFICATION_COMMANDS.md'
        content=guide.read_text(encoding='utf-8') if guide.exists() else 'Testing guide not available in this project package.'
        import re
        starts=list(re.finditer(r'^## (.+)$',content,flags=re.MULTILINE))
        sections={'Overview':content[:starts[0].start()].strip() if starts else content}
        for idx,m in enumerate(starts):
            end=starts[idx+1].start() if idx+1<len(starts) else len(content)
            sections[m.group(1)]=content[m.start():end].strip()
        self.test_guide_sections=sections
        self.test_guide_selection=tk.StringVar(value='Overview')
        row=ttk.Frame(parent);row.pack(fill='x',padx=15,pady=(14,8))
        ttk.Label(row,text='Assessment / test:').pack(side='left',padx=(0,6))
        choice=ttk.Combobox(row,textvariable=self.test_guide_selection,
                            values=list(sections),state='readonly',width=45)
        choice.pack(side='left',padx=(0,12))
        choice.bind('<<ComboboxSelected>>',lambda _e:self._show_command_section())
        ttk.Button(row,text='Copy command(s)',command=self._copy_command_section).pack(side='right',padx=(5,0))
        ttk.Button(row,text='Copy selection',command=self._copy_command_selection).pack(side='right',padx=5)
        self.test_commands_text=scrolledtext.ScrolledText(parent,wrap='word',
                           font=('Consolas',10),bg='#f8fafc',fg='#17354d',padx=18,pady=12)
        self.test_commands_text.pack(fill='both',expand=True,padx=15,pady=(0,10))
        ttk.Label(parent,text='Commands also documented in docs/TEST_AND_VERIFICATION_COMMANDS.md. Copy only the relevant block; replace example paths and COM4 as needed.',
                  wraplength=1120,justify='left').pack(fill='x',padx=20,pady=(0,12))
        self._show_command_section()

    def _show_command_section(self):
        import re
        value=self.test_guide_sections[self.test_guide_selection.get()]
        # Text widget shows readable prose and code, not literal Markdown markup.
        display=re.sub(r'(?m)^##\s+', '', value)
        display=re.sub(r'(?m)^```(?:powershell|tcl|text)?\s*$', '', display)
        display=display.replace('**','').replace('`','')
        display=re.sub(r'\n{3,}', '\n\n', display).strip()
        self.test_commands_text.configure(state='normal')
        self.test_commands_text.delete('1.0','end')
        self.test_commands_text.insert('1.0',display)
        self.test_commands_text.configure(state='disabled')

    def _copy_command_section(self):
        import re
        value=self.test_guide_sections[self.test_guide_selection.get()]
        blocks=re.findall(r'```(?:powershell|tcl|text)?\n(.*?)```',value,re.DOTALL)
        if not blocks:
            messagebox.showinfo('No runnable commands','Select a category containing a command block.');return
        selected='\n\n'.join(block.strip() for block in blocks)
        self.window.clipboard_clear();self.window.clipboard_append(selected)
        self.status.set('Copied testing command block(s) to clipboard; review comments/paths before executing.')

    def _copy_command_selection(self):
        try: selected=self.test_commands_text.get('sel.first','sel.last')
        except tk.TclError:
            messagebox.showinfo('Select text','Highlight a command in the guide first.');return
        self.window.clipboard_clear();self.window.clipboard_append(selected)
        self.status.set('Copied selected testing text to clipboard.')

    def _update_profile_comparison(self,result,*,label='CURRENT software-reference comparison'):
        normal=result['profiles']['normal'];strong=result['profiles']['strong']
        labels=(('X trajectory high-frequency reduction','x_pct'),
                ('Y trajectory high-frequency reduction','y_pct'),
                ('Roll trajectory high-frequency reduction','roll_pct'),
                ('Image area retained','crop_area_retained_pct'))
        table=self.profile_comparison_table
        for item in table.get_children():table.delete(item)
        for name,key in labels:
            table.insert('', 'end', values=(name,f'{normal[key]:.2f}%',f'{strong[key]:.2f}%'))
        table.insert('','end',values=('Independent image registration',
            normal.get('image_registration_status','UNKNOWN'),
            strong.get('image_registration_status','UNKNOWN')))
        digest=result.get('input_sha256','unknown')
        self.profile_source_label.set(f'{label}: {result.get("input_file", "unspecified")}  |  SHA-256: {digest[:16]}… (full hash in JSON report)')
        self.profile_provenance_label.set('SOFTWARE REFERENCE ONLY — NOT A PHYSICAL FPGA MEASUREMENT')
        self.profile_interpretation.set(result.get('interpretation','')+' '+result.get('limitations',''))

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
        self.help_subtabs.select(0)
        if tab in ('Testing & commands','Test commands'):
            self.help_subtabs.select(1)
            return
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
        ttk.Label(field,text='Duration (seconds, max 50):').pack(side='left',padx=10)
        durationvar=tk.StringVar(value='5')
        ttk.Entry(field,textvariable=durationvar,width=8).pack(side='left',padx=4)
        ttk.Label(body,text='The source must contain enough stationary background texture. In some sea-only clips the motion estimate may be inconclusive. This will be reported rather than hidden.',wraplength=690,foreground='#8b4c35').pack(anchor='w',pady=(10,7))
        def choose():
            filename=filedialog.askopenfilename(parent=win,title='Choose the ORIGINAL recorded video',
                filetypes=[('Camera recordings','*.mp4 *.mov *.avi *.m4v *.webm *.mkv'),('All files','*.*')])
            if not filename:return
            try:
                starttime=float(startvar.get())
                seconds=float(durationvar.get())
                if starttime<0 or seconds<.6 or seconds>50:raise ValueError('Start must be positive, and duration 0.6..50 seconds')
                probe_raw(Path(filename))
            except Exception as e:
                messagebox.showerror('Invalid footage',str(e),parent=win);return
            win.destroy()
            self._set_busy(True)
            self.status.set('Importing original camera recording without adding shake…')
            threading.Thread(target=self._natural_import_worker,args=(Path(filename),starttime,seconds),daemon=True).start()
        ttk.Button(body,text='Choose ORIGINAL recording and prepare',style='Accent.TButton',command=choose).pack(anchor='w',pady=12)
        ttk.Button(body,text='Cancel',command=win.destroy).pack(anchor='e')

    def _natural_import_worker(self,path:Path,start_s:float,duration_s:float):
        try:
            import datetime
            tag=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            folder=ROOT/'videos'
            data=prepare_natural_footage(path,folder/('import_'+tag+'_30fps.mp4'),start_s=start_s,duration_s=duration_s)
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
        path=filedialog.askopenfilename(title='Select 30-fps ship camera video',initialdir=str(ROOT/'videos'),filetypes=[('Video files','*.mp4 *.mov *.avi *.m4v'),('All files','*.*')])
        if not path:return
        try:info=inspect_video(Path(path))
        except Exception as e:messagebox.showerror('Video not supported',str(e));return
        self.source=Path(path)
        self.trajectory=None
        self.processing_mode.set('Video + Audio' if source_has_audio(self.source) else 'Video only')
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
            self.processing_mode.set('Video only')
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

    _STAGE_LABELS = {
        'motion_estimation':'Estimating camera X/Y/roll from the video',
        'motion_fir':'Filtering motion trajectory (FPGA UART or software)',
        'video_render':'Rendering and warping video frames on PC',
        'visual_assessment':'Independent image-stability assessment',
        'audio_decode':'Decoding audio on PC',
        'audio_fir':'Filtering audio samples (FPGA UART or software)',
        'audio_enhancement':'Host adaptive audio processing',
        'media_export':'Exporting combined MP4 on PC',
        'profile_compare':'Comparing software smoothing profiles',
    }
    _STAGE_RANGES = {
        'motion_estimation':(0,18), 'motion_fir':(18,34),
        'video_render':(34,51),'visual_assessment':(51,57),
        'audio_decode':(57,59),'audio_fir':(59,93),
        'audio_enhancement':(93,96),'media_export':(96,100),
        'profile_compare':(0,100)
    }

    def _progress_ui(self, stage, done, total):
        label=self._STAGE_LABELS.get(stage,stage)
        start,end=self._STAGE_RANGES.get(stage,(0,100))
        fraction=max(0.,min(1.,done/max(1,total)))
        pct=start+(end-start)*fraction
        if not self._job_has_audio and not self._job_is_comparison:
            pct=100*min(1.,pct/57.)
        self.progress_pct.set(min(100,pct))
        elapsed=max(0.,time.monotonic()-self._job_started)
        self.progress_label.set(f'{label}: {done:,}/{total:,}  •  {elapsed:.0f}s elapsed')

    def request_cancel(self):
        """Request cancellation; leave any in-flight UART packet intact."""
        if self._job_is_processing and self._cancel_event is not None and self.busy:
            self._cancel_event.set()
            self.cancel_btn.configure(state='disabled')
            self.progress_label.set('Cancellation requested — waiting for a safe checkpoint')
            self.status.set('Cancellation requested; the current FPGA packet will finish first. Do not reset the board.')

    def _set_busy(self,v):
        self.busy=v
        state='disabled' if v else 'normal'
        for widget in [self.hw_btn,self.sw_btn,self.demo_btn,self.open_btn,self.csv_btn,self.test_btn,self.real_btn,self.compare_btn]:
            widget.configure(state=state)
        self.processing_combo.configure(state='disabled' if v else 'readonly')
        self.cancel_btn.configure(state=('normal' if v and self._job_is_processing else 'disabled'))

    def process(self,hardware:bool):
        if self.busy:return
        try:self._validate_selected()
        except Exception as e:messagebox.showerror('No valid input',str(e));return
        port=self.comport.get().strip().upper() if hardware else None
        if hardware and not port:
            messagebox.showerror('No COM port','Connect the programmed Arty A7 and select its UART COM port (COM4 in your successful test).');return
        if not hardware and not messagebox.askyesno('Software only','This mode will NOT communicate with the FPGA and will be labelled SOFTWARE REFERENCE ONLY. Continue?'):
            return
        if self.processing_mode.get() == 'Video + Audio' and not source_has_audio(self.source):
            messagebox.showerror('No soundtrack', 'This source has no audio track. Select Video only to stabilise the images.');return
        self._clear_result()
        self._cancel_event = threading.Event()
        self._job_is_processing = True
        self._job_has_audio = self.processing_mode.get() == 'Video + Audio'
        self._job_is_comparison = False
        self._job_started = time.monotonic()
        self.progress_pct.set(0)
        self.progress_label.set('Preparing processing run …')
        self._set_busy(True)
        self.status.set(('Sending motion data to the real Arty A7 on '+port if hardware else 'Running software-only preview')+' …')
        self.validation.set('Processing in progress — no results yet')
        mode=('PHYSICAL FPGA (COM '+port+')' if hardware else 'SOFTWARE REFERENCE (no FPGA)')
        self.assessment_context.set(
            f'Source: {self.source.name if self.source else "none"}   |   Assessment: PROCESSING — {mode}   |   {self.processing_mode.get()}')
        base=ROOT/'videos'/('hrd' if hardware else 'sim')
        import datetime
        dest=base/(datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+('_hardware' if hardware else '_software'))
        t=threading.Thread(target=self._process_thread,args=(self.source,self.trajectory,dest,port,self.profile.get(),self.processing_mode.get(),self.audio_cleanup_mode.get(),self._cancel_event),daemon=True)
        t.start()

    def _process_thread(self,source,trajectory,dest,port,profile,processing='Video only',audio_cleanup='Maritime adaptive',cancel_event=None):
        def report(stage, done, total):
            # Keep UI event queue bounded on long video jobs.
            now=time.monotonic()
            if done == total or now-self._last_progress_emit >= .15:
                self._last_progress_emit=now
                self.events.put(('progress',(stage,done,total)))
        try:
            if processing == 'Video + Audio':
                result=run_unified_pipeline(source,trajectory,dest,port,profile=profile,
                    processing=processing,audio_cleanup=audio_cleanup,cancel_event=cancel_event,progress=report)
            else:
                result=run_pipeline(source,trajectory,dest,port,profile=profile,cancel_event=cancel_event,progress=report)
                result.metrics['combined_processing']='Video only'
            self.events.put(('result',result))
        except ProcessingCancelled:
            import datetime
            dest.mkdir(parents=True,exist_ok=True)
            (dest/'CANCELLED.json').write_text(json.dumps({
                'status':'CANCELLED_NOT_VERIFIED',
                'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'source':Path(source).name,'hardware_requested':bool(port),
                'note':'Stopped between complete UART transactions; partial artifacts are NOT verified.'
            },indent=2)+'\n',encoding='utf-8')
            self.events.put(('cancelled',str(dest)))
        except Exception as e:self.events.put(('error',(str(e),traceback.format_exc())))

    def compare_smoothing(self):
        """Run both profiles on the same source in an isolated reference-only job."""
        if self.busy:return
        try:self._validate_selected()
        except Exception as ex:messagebox.showerror('Invalid video',str(ex));return
        import datetime
        folder=ROOT/'verification'/'system'/'generated'/'profile_comparisons'/(
             datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        self._cancel_event=threading.Event()
        self._job_is_processing=True
        self._job_is_comparison=True
        self._job_has_audio=False
        self._job_started=time.monotonic()
        self.progress_pct.set(0)
        self.progress_label.set('Comparing Normal vs Strong (software reference only)')
        self.profile_comparison_text.set('Comparison running on PC; real FPGA not used')
        self._set_busy(True)
        threading.Thread(target=self._compare_smoothing_worker,
            args=(self.source,self.trajectory,folder,self._cancel_event),daemon=True).start()

    def _compare_smoothing_worker(self,source,trajectory,folder,cancel_event):
        try:
            result=compare_profiles(source,trajectory,folder,cancel_event=cancel_event,
                progress=lambda stage,done,total:self.events.put(('progress',(stage,done,total))))
            self.events.put(('profile_comparison_result',(result,str(folder))))
        except ProcessingCancelled:
            folder.mkdir(parents=True,exist_ok=True)
            (folder/'CANCELLED.json').write_text(json.dumps({'status':'CANCELLED_NOT_VERIFIED',
                'note':'Software comparison did not finish; partial results are not qualified.'})+'\n',encoding='utf-8')
            self.events.put(('cancelled',str(folder)))
        except Exception as exc:
            self.events.put(('error',(str(exc),traceback.format_exc())))

    def hardware_test(self):
        if self.busy:return
        port=self.comport.get().strip().upper()
        if not port:
            messagebox.showwarning('No COM port','Select your Arty A7 UART port first.');return
        self._set_busy(True)
        self.status.set('Verifying motion FIR and, in combined mode, the audio coefficient bank on '+port+' …')
        threading.Thread(target=self._hardware_test_thread,args=(port,self.processing_mode.get()),daemon=True).start()

    def _hardware_test_thread(self,port,processing='Video only'):
        try:
            cases={'impulse':[32768]+[0]*31,'negative_dc':[-3840]*64,
                   'mixed_sign':[(-1 if i%2 else 1)*(23000+(i*8899)%33000) for i in range(80)]}
            count=0
            for idx,(name,samples) in enumerate(cases.items(),1):
                expected=FirReference().process(samples)
                got=run_batch(port,samples,idx)
                if got!=expected:raise AssertionError(f'Hardware FIR mismatch in {name}')
                count+=1
                self.events.put(('info',f'PASS PHYSICAL FPGA {name}: {len(samples)} bit-exact samples'))
            if processing == 'Video + Audio':
                # Fail early if an old video-only bitstream is programmed.
                from design_audio_coefficients import design
                audio_samples=[0]*25+[24000,-12000,8000,-4000]+[0]*35
                expected=FirReference(design()).process(audio_samples)
                got=run_batch(port,audio_samples,0x81)
                if got!=expected:raise AssertionError('Wrong audio coefficient bank. Build and program v0.9+ bitstream.')
                count+=1
                self.events.put(('info',f'PASS PHYSICAL FPGA audio bank: {len(audio_samples)} bit-exact samples'))
            self.events.put(('hardware_pass',(port,count)))
        except Exception as e:self.events.put(('error',(str(e),traceback.format_exc())))

    def _poll_events(self):
        try:
            while True:
                kind,payload=self.events.get_nowait()
                if kind=='info':self._log(payload)
                elif kind=='progress':
                    if self._job_is_processing and not (self._cancel_event and self._cancel_event.is_set()):
                        self._progress_ui(*payload)
                elif kind=='profile_comparison_result':
                    self._set_busy(False)
                    self._job_is_processing=False
                    self._job_is_comparison=False
                    self._cancel_event=None
                    result,folder=payload
                    a=result['profiles']['normal'];b=result['profiles']['strong']
                    text=(f"Normal X/Y/Roll: {a['x_pct']:.1f}/{a['y_pct']:.1f}/{a['roll_pct']:.1f}% | "
                          f"Strong: {b['x_pct']:.1f}/{b['y_pct']:.1f}/{b['roll_pct']:.1f}% | "
                          f"Crop: {a['crop_area_retained_pct']:.1f}% / {b['crop_area_retained_pct']:.1f}%")
                    self.profile_comparison_text.set(text)
                    self.profile_comparison_file=Path(folder)/'profile_comparison.json'
                    self._update_profile_comparison(result)
                    self.assess_view.set('Profile comparison')
                    self._show_assessment_view()
                    self.progress_pct.set(100)
                    self.progress_label.set('Software profile comparison complete')
                    self._log('PROFILE COMPARISON (SOFTWARE): '+json.dumps(result,indent=2))
                    self.status.set('Comparison saved. Open Video Assessment for details; no FPGA data altered.')
                    messagebox.showinfo('Software reference profile comparison',
                        text+'\n\nIndependent image registration: '+
                        a['image_registration_status']+' / '+b['image_registration_status']+
                        '\n\nNo verified visual improvement claim. Reports: '+folder)
                elif kind=='cancelled':
                    self._set_busy(False)
                    self._job_is_processing=False
                    self._job_is_comparison=False
                    self._cancel_event=None
                    self.progress_label.set('Cancelled; partial outputs are not verified')
                    self.validation.set('CANCELLED — NO FPGA OR VISUAL PASS CLAIM')
                    self.status.set('Processing cancelled safely. The FPGA was not reset. Ready for next job.')
                    self._log('OPERATOR CANCELLED: '+payload)
                elif kind=='hardware_pass':
                    self._set_busy(False)
                    verified_port,number=payload
                    self.validation.set(f'PHYSICAL FPGA UART/FIR TEST PASS — {verified_port}: {number}/{number} cases, bit-exact (no video assessment)')
                    self.assessment_context.set(
                        f'Source: {self.source.name if self.source else "none"}   |   Assessment: NOT RUN — FPGA connection only verified')
                    self.status.set('Hardware connected and numerical test passed. Select a video and process it.')
                elif kind=='error':
                    self._set_busy(False)
                    self._job_is_processing=False
                    self._job_is_comparison=False
                    self._cancel_event=None
                    self.progress_label.set('Processing failed; see Evidence log')
                    message,detail=payload
                    self._log('ERROR: '+detail)
                    self.validation.set('FAILED / UNVERIFIED — no hardware success claim')
                    self.status.set('Processing failed. Open Assessment → Evidence log for details.')
                    messagebox.showerror('Processing failed',message)
                elif kind=='natural_import':
                    self._set_busy(False)
                    self.source=Path(payload[0]);self.trajectory=None;self.input_kind='NATURAL'
                    self.processing_mode.set('Video + Audio' if source_has_audio(self.source) else 'Video only')
                    info=inspect_video(self.source)
                    self.video_info.set(f'NATURAL VIDEO (USER SUPPLIED) | {info.width}×{info.height} | {info.fps:.1f} fps | {info.frames} frames')
                    self.motion_mode.set('NATURAL CAMERA MOVEMENT: estimate trajectory from footage; no artificial shake or CSV')
                    self._clear_result();self._show_source_frame()
                    self.status.set('Natural recording prepared. Ready for automatic motion estimation and physical FPGA filtering.')
                    self._log('Natural footage prepared without synthetic shake: '+str(self.source))
                    self._log('Source provenance: '+str(self.source.parent/(self.source.stem+'_source_provenance.json')))
                elif kind=='result':
                    self._set_busy(False)
                    self._job_is_processing=False
                    self._job_is_comparison=False
                    self._cancel_event=None
                    self.progress_pct.set(100)
                    self.progress_label.set(f'Complete — {max(0.,time.monotonic()-self._job_started):.1f}s elapsed')
                    self._accept_result(payload)
        except queue.Empty:pass
        self.window.after(70,self._poll_events)

    def _accept_result(self,result):
        self.result=result
        if hasattr(self,'after_title'):
            hybrid=result.metrics.get('hybrid_host_audio_enhancement', False)
            label=('FPGA FIR + PC AUDIO DENOISER — HYBRID' if hybrid else 'FPGA FILTERED — BIT-EXACT') if result.metrics.get('hardware_verified') else 'SOFTWARE PREVIEW — NOT FPGA'
            self.after_title.configure(text=label)
        m=result.metrics
        mode=('PHYSICAL FPGA / bit-exact' if m.get('hardware_verified') else 'SOFTWARE REFERENCE / no FPGA')
        audio_mode=m.get('audio_filtering',{}).get('status','NOT REQUESTED')
        self.assessment_context.set(
            f"Source: {result.video.name}   |   Video: {mode}   |   Audio: {audio_mode}   |   {m.get('profile', 'Normal')}")
        audio_info=m.get('audio_filtering',{})
        analysis=audio_info.get('analysis',{})
        self.audio_context.set(f"Source: {result.video.name}   |   Audio: {audio_info.get('status','NOT REQUESTED')}")
        self.audio_stage.set('Final soundtrack: '+audio_info.get('final_audio_processing','No audio processing requested'))
        def band(x): return f'{x:+.2f} dB' if isinstance(x,(int,float)) else 'N/A'
        self.audio_high.set(band(analysis.get('high_band_5_7k5_attenuation_db')))
        self.audio_mid.set(band(analysis.get('speech_band_250_3000_change_db')))
        self.audio_rumble.set(band(analysis.get('rumble_band_40_180_change_db')))
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
        if m.get('combined_output'):
            self._log('FINAL STABILISED VIDEO + FILTERED AUDIO: '+str(result.output_dir/m['combined_output']))
            self.status.set('Video + audio complete. Press Play for synchronized sound; Audio: Filtered selected.')
        else:
            self.status.set('Video stabilisation complete. The original soundtrack was retained.')
        self.draw_plots()
        self.draw_image_metric()
        self.draw_audio_metric()
        self.refresh_summary_report()
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
        filtered_available = bool(kind == 'pair' and self.result and
                                  (self.result.output_dir/'audio_filtered.wav').exists())
        self.audio_combo.configure(values=('Original','Filtered','Mute') if filtered_available
                                   else ('Original','Mute'))
        self.audio_choice.set('Filtered' if filtered_available else 'Original')
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
        self.soundtrack.stop()
        if self.capture is not None and self.frames > 0 and self.frame_idx >= self.frames - 1:
            self.play_btn.configure(text='↻ Replay')
        else:
            self.play_btn.configure(text='▶ Play')

    def _audio_media(self) -> Path | None:
        """One selectable soundtrack, never mix original and filtered speakers."""
        if self.audio_choice.get() == 'Mute':
            return None
        if self._playback_kind == 'source' and self.source is not None and not source_has_audio(self.source):
            return None
        if self._playback_kind == 'pair' and self.result:
            filename = ('audio_filtered.wav' if self.audio_choice.get() == 'Filtered'
                        else 'audio_original.wav')
            candidate = self.result.output_dir / filename
            if candidate.exists():
                return candidate
            if self.audio_choice.get() == 'Filtered':
                return self.result.side_by_side
        return self.source

    def _change_audio_choice(self, _event=None) -> None:
        """Changing audio track restarts at the currently displayed frame."""
        if self.playing:
            self._pause_playback()
            self.toggle_play()
        else:
            self.status.set(f'Audio track selected: {self.audio_choice.get()}. Press Play to listen.')

    def _schedule_play_tick(self) -> None:
        if self.playing and self._play_after_id is None:
            self._play_after_id = self.window.after(15,self._play_tick)

    def toggle_play(self) -> None:
        if self.capture is None or self.frames < 1:
            return
        if self.playing:
            self._pause_playback()
            return
        if self.frame_idx >= self.frames - 1:
            self._show_frame(0)
        # An audio track starts at the same media timestamp as the first frame.
        # Audio is rendered by Windows; Tk frames follow a monotonic timeline.
        audio = self._audio_media()
        if audio is not None and self.soundtrack.supported:
            try:
                self.soundtrack.play(audio, self.frame_idx/self.fps)
                details = self.soundtrack.last_playback or {}
                self.status.set(f'Playing {self.audio_choice.get()} soundtrack '
                                f'({details.get("backend", "audio output")}). Video and sound are synchronized.')
                self._log('AUDIO PLAYBACK: ' + json.dumps(details, sort_keys=True))
            except Exception as exc:
                self._log(f'AUDIO PLAYBACK FAILED: {type(exc).__name__}: {exc}')
                self.status.set(f'Audio playback FAILED: {exc}. Use Play MP4 with audio to compare.')
        elif audio is not None and not self.soundtrack.supported:
            self.status.set('Embedded sound is supported on Windows; use Play MP4 with audio here.')
        elif self.audio_choice.get() != 'Mute':
            self.status.set('No selectable soundtrack found. Check generated audio WAV files in Results folder.')
        self._play_start = time.monotonic()
        self._play_start_frame = self.frame_idx
        self.playing = True
        self.play_btn.configure(text='❚❚ Pause')
        self._schedule_play_tick()

    def _play_tick(self) -> None:
        self._play_after_id = None
        if not self.playing or self.capture is None:
            return
        # Frame index is derived from time, not number of Tk callbacks: a
        # slow redraw can drop frames rather than desynchronise soundtrack.
        seconds = max(0.,time.monotonic()-self._play_start)
        target = self._play_start_frame+int(seconds*self.fps)
        if target >= self.frames:
            target = self.frames-1
        if target != self.frame_idx:
            self._show_frame(target)
        if self.playing:
            if target >= self.frames - 1:
                self._pause_playback()
            else:
                self._schedule_play_tick()

    def _seek_press(self, event=None) -> None:
        if self.playing:
            self._pause_playback()

    def _seek_release(self, event=None) -> None:
        if self.capture is not None:
            self._show_frame(round(self.seek_pos.get()))
            self._pause_playback()

    def draw_audio_metric(self):
        """Audio-spectrum plot from saved WAVs, not a claim of speech quality."""
        ax=self.audioax
        ax.clear()
        if self.result is None or not (self.result.output_dir/'audio_filtered.wav').exists():
            ax.text(.5,.5,'Audio spectrum appears after Video + Audio processing',
                    ha='center',va='center',transform=ax.transAxes)
        else:
            import wave
            for filename,label,color in [('audio_original.wav','Original audio','#597e98'),
                                         ('audio_fir_only.wav','FIR-only stage (FPGA or reference)','#b88726'),
                                         ('audio_filtered.wav','Final audio (adaptive host if selected)','#07899b')]:
                if not (self.result.output_dir/filename).exists(): continue
                with wave.open(str(self.result.output_dir/filename),'rb') as wav:
                    rate=wav.getframerate()
                    raw=wav.readframes(wav.getnframes())
                a=np.frombuffer(raw,dtype='<i2').astype(np.float64)
                a-=a.mean()
                # Window a bounded first 4s for readable frequency resolution
                a=a[:min(len(a),rate*4)]
                if not len(a):continue
                freq=np.fft.rfftfreq(len(a),1/rate)
                amp=np.abs(np.fft.rfft(a*np.hanning(len(a))))
                ax.plot(freq,20*np.log10(np.maximum(amp,1e-9)),label=label,color=color,linewidth=1.4)
            ax.axvline(3200,linestyle='--',alpha=.4,label='Nominal 3.2 kHz cutoff')
            ax.set(xlim=(0,8000),xlabel='Audio frequency (Hz)',ylabel='Relative magnitude (dB)',
                   title='Audio spectrum, first 4 seconds — FPGA FIR vs HOST cleanup are distinct')
            ax.grid(alpha=.2);ax.legend(loc='best')
        self.audiofig.subplots_adjust(left=.09,right=.97,bottom=.18,top=.86)
        self.audiocanvas.draw_idle()

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
        self.validation.set('No video processing performed')
        filename=self.source.name if self.source else 'none'
        self.assessment_context.set(f'Source: {filename}   |   Video assessment: NOT RUN — original video only')
        self.audio_context.set(f'Source: {filename}   |   Audio assessment: NOT RUN')
        self.audio_stage.set('Audio FIR: not run')
        for v in [self.audio_high,self.audio_mid,self.audio_rumble]: v.set('—')
        self.image_metric.set('Independent image stability: not assessed')
        self.draw_plots()
        self.draw_image_metric()
        self.draw_audio_metric()
        self.play_btn.configure(state='disabled')
        self.frame_text.configure(text='0 / 0')

    def reset_view(self):
        if self.busy:
            messagebox.showwarning('Busy','Cannot reset view during an active UART/video job.');return
        self._clear_result()
        if self.source:self._show_source_frame()
        self.status.set('View cleared. FPGA hardware itself is unchanged; use BTN0 for a physical reset if required.')
        self._log('GUI reset view (does NOT reset the FPGA).')

    def open_audio_dialog(self):
        """Audio v0.9 prototype — separate UI, preserving the three main tabs."""
        if self._audio_window is not None and self._audio_window.winfo_exists():
            self._audio_window.lift()
            return
        import datetime
        from audio_dsp import process
        win=tk.Toplevel(self.window)
        self._audio_window=win
        win.title('Maritime DSP — Audio noise reduction (v0.9)')
        win.geometry('840x530')
        win.minsize(720,480)
        box=ttk.Frame(win,padding=16);box.pack(fill='both',expand=True)
        ttk.Label(box,text='OFFLINE AUDIO FILTER  /  16 kHz SPEECH BAND',
                  font=('Segoe UI',15,'bold')).pack(anchor='w',pady=(0,10))
        ttk.Label(box,text='Low-pass FIR: reduces high-frequency hiss; not an engine-noise separator. '
                  'Software preview requires no FPGA. Physical mode requires the new v0.9 bitstream.',
                  wraplength=790).pack(anchor='w',pady=(0,12))
        source=tk.StringVar(value=str(self.source) if self.source is not None else '')
        row=ttk.Frame(box);row.pack(fill='x',pady=(0,10))
        ttk.Label(row,text='Source WAV / MP4').pack(side='left',padx=(0,8))
        ttk.Entry(row,textvariable=source).pack(side='left',fill='x',expand=True,padx=(0,6))
        def browse():
            selected=filedialog.askopenfilename(parent=win,title='Choose media with an audio track',
                initialdir=str(ROOT/'videos'),filetypes=[('Audio/video','*.wav *.mp3 *.m4a *.mp4 *.mov *.mkv'),('All files','*.*')])
            if selected:source.set(selected)
        ttk.Button(row,text='Browse…',command=browse).pack(side='left')
        opts=ttk.Frame(box);opts.pack(fill='x',pady=(0,13))
        ttk.Label(opts,text='Start (seconds)').pack(side='left',padx=(0,5))
        start=tk.StringVar(value='0')
        ttk.Entry(opts,textvariable=start,width=7).pack(side='left',padx=(0,16))
        ttk.Label(opts,text='Duration (seconds)').pack(side='left',padx=(0,5))
        seconds=tk.StringVar(value='4')
        ttk.Entry(opts,textvariable=seconds,width=7).pack(side='left',padx=(0,16))
        ttk.Label(opts,text='Hardware UART: '+(self.comport.get() or '(select COM in main GUI)')) .pack(side='left')
        status=tk.StringVar(value='Select an audio source, then process with software or FPGA.')
        ttk.Label(box,textvariable=status,wraplength=780,foreground='#086a83').pack(fill='x',pady=(0,8))
        report=scrolledtext.ScrolledText(box,height=9,wrap='word',font=('Consolas',10))
        report.pack(fill='both',expand=True,pady=(3,8))
        result_dir={'path':None}
        queue_audio=queue.Queue()
        buttons=ttk.Frame(box);buttons.pack(fill='x')
        def play(filename):
            if not result_dir['path']:
                messagebox.showinfo('Process first','Run audio filtering before playback.',parent=win);return
            target=result_dir['path']/filename
            if not target.is_file():
                messagebox.showerror('Missing audio',str(target),parent=win);return
            import os,subprocess
            if sys.platform=='win32' and target.suffix.lower()=='.wav':
                import winsound
                winsound.PlaySound(str(target),winsound.SND_FILENAME|winsound.SND_ASYNC)
            elif sys.platform=='win32':os.startfile(str(target))
            elif sys.platform=='darwin':subprocess.Popen(['open',str(target)])
            else:subprocess.Popen(['xdg-open',str(target)])
        def launch(hardware):
            try:
                path=Path(source.get().strip())
                if not path.is_file():raise ValueError('Select a valid media file')
                offset=float(start.get());duration=float(seconds.get())
                if not (0 <= offset <= 3600 and 0 < duration <= 30):
                    raise ValueError('Start >= 0 and duration must be <= 30 seconds')
                port=self.comport.get().strip() if hardware else None
                if hardware and not port:raise ValueError('Select your actual COM port in the main window')
                if hardware and not messagebox.askyesno('v0.9 hardware required',
                    'Audio mode requires the NEW v0.9 bitstream. The older video-only bitstream cannot filter speech. '
                    'Has the new bitstream been programmed?',parent=win):return
            except Exception as ex:
                messagebox.showerror('Invalid audio settings',str(ex),parent=win);return
            sw_btn.configure(state='disabled');hw_btn.configure(state='disabled')
            status.set('Processing audio via '+ ('PHYSICAL FPGA '+port if hardware else 'SOFTWARE REFERENCE')+'…')
            folder=ROOT/'videos'/('hrd' if hardware else 'sim')/('audio_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
            def worker():
                try:queue_audio.put(('ok',folder,process(path,folder,port=port,start_s=offset,duration_s=duration)))
                except Exception as ex:queue_audio.put(('err',str(ex),traceback.format_exc()))
            threading.Thread(target=worker,daemon=True).start()
            def check():
                if not win.winfo_exists():return
                try:item=queue_audio.get_nowait()
                except queue.Empty:win.after(160,check);return
                sw_btn.configure(state='normal');hw_btn.configure(state='normal')
                if item[0]=='err':
                    status.set('Audio processing FAILED — see details.')
                    report.insert('end',item[1]+'\n'+item[2]);return
                folder,metrics=item[1],item[2]
                result_dir['path']=folder
                a=metrics['analysis']
                status.set(metrics['processing_mode']+'  |  '+metrics['source'])
                report.delete('1.0','end')
                report.insert('end',f"Sample rate: {metrics['sample_rate_hz']} Hz, mono\n"
                    f"Samples: {metrics['samples']}\nFPGA jobs: {metrics['fpga_job_count']}\n"
                    f"High-band 5–7.5 kHz change: {a['high_band_5_7k5_attenuation_db']} dB\n"
                    f"Speech-band 250–3000 Hz change: {a['speech_band_250_3000_change_db']} dB\n"
                    f"Output folder: {folder}\n\n"
                    'A spectral reduction is NOT proof of improved speech intelligibility.\n')
            win.after(160,check)
        sw_btn=ttk.Button(buttons,text='Software audio preview',command=lambda:launch(False))
        sw_btn.pack(side='left',padx=(0,6))
        hw_btn=ttk.Button(buttons,text='Process on FPGA (new bitstream)',command=lambda:launch(True))
        hw_btn.pack(side='left',padx=(0,6))
        ttk.Button(buttons,text='▶ Original',command=lambda:play('audio_original.wav')).pack(side='left',padx=3)
        ttk.Button(buttons,text='▶ Filtered',command=lambda:play('audio_filtered.wav')).pack(side='left',padx=3)
        ttk.Button(buttons,text='▶ A/B',command=lambda:play('audio_AB_compare.wav')).pack(side='left',padx=3)
        ttk.Button(buttons,text='Close',command=win.destroy).pack(side='right')

    def open_media_with_audio(self):
        """Open the MP4 with its soundtrack in the external system media player."""
        path = self.result.side_by_side if self.result else self.source
        if path is None or not Path(path).is_file():
            messagebox.showinfo('Select video','Choose a source or process a video first.')
            return
        import os, subprocess
        if sys.platform == 'win32':
            os.startfile(str(path))
        elif sys.platform == 'darwin':
            subprocess.Popen(['open',str(path)])
        else:
            subprocess.Popen(['xdg-open',str(path)])

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
        self._pause_playback()
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
        if self.busy:
            if self._job_is_processing:
                if messagebox.askyesno('Processing is active',
                    'Request a safe cancel and keep this window open until the current UART transaction finishes?'):
                    self.request_cancel()
                return
            messagebox.showwarning('Operation active','Allow the FPGA verification or import operation to finish before closing.')
            return
        self._release_video();self.soundtrack.close();self.window.destroy()


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
