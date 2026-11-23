"""Stand-alone operator help for FPGA motion stabilisation, no web dependency."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

HELP_SECTIONS=[
('Quick start', '''MARITIME FPGA STABILISATION — NATURALLY SHAKY FOOTAGE

1. Connect the Arty A7-35T and configure its existing verified bitstream
   through Vivado Hardware Manager if it was powered down/reconfigured.
2. Choose Normal (one FIR pass) or Strong (two FIR passes).
   Both profiles use the same programmed FPGA bitstream.
3. In this application, click Detect COM ports and select the board's port.
   COM4 worked on one development PC; it is NOT a universal value.
4. Press Verify FPGA connection & FIR; the 3 bit-exact tests must pass.
5. Click Import natural footage… and choose a genuine camera recording.
   This imports a short 30fps segment with NO added shake or CSV.
6. Click Stabilise Video Using FPGA. The PC estimates camera X/Y and roll from
   actual footage, sends X/Y/roll samples to the FPGA FIR, reads them back
   and verifies every returned sample against its bit-exact reference.
7. Before processing, you can play/replay the original video on its own.
   After processing, play ORIGINAL / STABILISED views together. Inspect trajectory and
   spectrum graphs, then see independent image-content registration result.
8. Open result folder to retain the video, plots, CSV and evidence report.

Unlike synthetic tests, the independent image-content result may be
INCONCLUSIVE or NEGATIVE. A positive result is not guaranteed.

Software preview only is NOT physical FPGA evidence.'''),
('Every control', '''MAIN CONTROLS

Open video…
  Use an already compatible 30fps MP4/MOV/AVI/M4V, <1280x720,
  18–1500 frames (0.6–50 s). Motion is automatically estimated; no CSV is used.

Import natural footage…
  Select the ORIGINAL camera recording (MP4, MOV, WEBM, MKV, AVI).
  Prepare a maximum five-second 960x540, 30fps clip from your chosen
  start time. Temporal selection, resampling and letterboxing ONLY.
  Does NOT add any camera shake and does NOT create motion CSV.

Generate synthetic test video
  Independent numeric regression only; creates animated test signal.
  Do not present this as evidence of performance on real footage.

Lab test: trajectory CSV…
  Available ONLY for generated synthetic bench tests. The real-video
  path deliberately rejects manual CSV input.

Detect COM ports
  List Windows COM ports. Does not program FPGA or prove correct bitstream.

Verify FPGA connection & FIR
  Sends impulse, negative DC and mixed-sign samples. Every result must
  match the independent Python model bit-for-bit before hardware claims.

Stabilise Video Using FPGA
  PC decodes video/estimates motion; FPGA filters X/Y and roll trajectories;
  PC warp-reconstructs two synchronized views and exports evidence.
  Normal = one FIR pass. Strong = two FIR passes for more smoothing.
  The progress strip shows stages and approximate completion, not ETA.
  Cancel processing requests a safe stop BETWEEN complete UART packets;
  do not press FPGA BTN0 during processing or cancel.
  Excessive smoothing may crop more image or suppress deliberate camera motion.

Software preview only
  Python numerical reference. CLEARLY NOT FPGA hardware evidence.

Video Assessment -> Compare Normal / Strong
  Re-run the two smoothing profiles entirely in software, showing
  X/Y/roll trajectory reductions, crop retention and independently
  measured image registration. May be INCONCLUSIVE on maritime footage.
  Never claim profile comparisons are a new FPGA physical test.

Reset view
  Clears GUI only, NOT physical FPGA; each new job resets FIR history.

Play/Pause/Replay and seek bar
  Opening a video enables immediate original-only playback (left panel).
  The right panel stays empty until a hardware or software processing job.
  At the end of a video, click Replay to return to the start and play again.
  Pause and drag the seek bar to inspect any frame.

Plots and export
  After processing, inspect synchronized original/stabilised frames and quantitative
  filtering results. A second IMAGE-based measure validates displayed
  video jitter independently of numeric FIR trajectory smoothing.
'''),
('Program Arty A7', '''PROGRAM PHYSICAL FPGA WITH VIVADO 2025.2.1

The GUI does NOT have JTAG/FPGA programming access.

1. Connect the Arty A7-35T to USB and power it on.
2. Open Vivado Hardware Manager → Open target → Auto Connect.
3. Check detected device is xc7a35t_0.
4. Click Program device and browse to this working directory:
   hardware\\build\\maritime_a7.runs\\impl_1\\arty_a7_maritime_top.bit
5. Program and check startup status is HIGH. No ILA debug cores is normal.
6. Close Hardware Manager if it holds resources, open GUI, Detect COM
   ports, choose the board port (COM4 was used in prior testing).
7. Run Verify FPGA connection & FIR (3 cases) before a real-video job.

Reprogram after loss of volatile configuration, power cycling, or
loading a different bitstream. BTN0 is board reset; usually no press
is needed between jobs. Reset view in GUI never resets the FPGA.
'''),
('Natural footage & evidence', '''REAL-WORLD VALIDATION RULES

PRIMARY TEST: Use an actual video recorded with camera on a moving
vessel, with NATURALLY OCCURRING camera shake. No artificial motion
injection, no supplied motion CSV, no synthetic camera movement.

SOURCE SUGGESTIONS
  MODD2 (ViCoS Lab): 28 recorded USV sequences, two with abrupt roll
  and pitch. Dataset is large (~6GB):
  https://data.vicos.si/borja/viamaro/index.html
  You may also import your own legitimate boat-mounted video or an
  appropriately licensed openly available recording.

SOURCE RIGHTS
  Confirm permissions before sharing or publishing video data.
  This project does not include raw third-party footage. Do not claim
  authorisation or commercial rights from a dataset's availability.

NORMALISATION
  Imported video is clipped, resized/letterboxed, converted to 30fps;
  no fake shake or stabilisation is applied before FPGA processing.
  A source SHA-256 and conversion manifest are saved locally.

VALIDATION
  1. FIR numeric output must match Python exactly for hardware PASS.
  2. Estimated trajectory HF RMS is an ALGORITHM diagnostic only.
  3. Independent image registration of ORIGINAL vs STABILISED pixels
     must support any image-stability claim. If too few stationary
     background features exist, display INCONCLUSIVE instead.
  4. A negative result remains negative; do not silently improve it
     using a precomputed CSV or label a software result as hardware.

LIMITS
  FPGA receives numeric 24-bit Q16.8 samples, not pixels.
  Global translation and in-plane roll are compensated, not pitch perspective,
  zoom, target's own movement or rolling-shutter effects.
  Buffered/offline, not live real-time camera streaming.
''')]


def open_help(parent: tk.Misc, existing=None):
    """Readable, scalable operator guide. Existing section names remain stable."""
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.lift();existing.focus_force();return existing
        except tk.TclError:pass
    w=tk.Toplevel(parent)
    w.title('Operator guide  |  Maritime FPGA DSP')
    w.geometry('1120x800');w.minsize(820,590)
    w.configure(bg='#edf3f8')

    header=tk.Frame(w,bg='#122e45',height=95)
    header.pack(fill='x');header.pack_propagate(False)
    tk.Label(header,text='OPERATOR GUIDE',font=('Segoe UI',21,'bold'),
             bg='#122e45',fg='white').pack(anchor='w',padx=26,pady=(12,0))
    tk.Label(header,text='Connection   •   FPGA programming   •   Video stabilisation   •   Evidence',
             font=('Segoe UI',11),bg='#122e45',fg='#c7dfeb').pack(anchor='w',padx=26,pady=(1,0))

    container=ttk.Frame(w,padding=(17,16,17,12))
    container.pack(fill='both',expand=True)
    bar=ttk.Frame(container);bar.pack(fill='x',pady=(0,8))
    ttk.Label(bar,text='Choose a topic below. Increase font size with A+ if needed.',
              font=('Segoe UI',11)).pack(side='left')
    text_widgets=[]
    sizes=[12]
    def resize(delta):
        sizes[0]=max(10,min(19,sizes[0]+delta))
        for txt in text_widgets:
            txt.configure(font=('Segoe UI',sizes[0]))
            txt.tag_configure('section',font=('Segoe UI',sizes[0]+2,'bold'))
            txt.tag_configure('step',font=('Segoe UI',sizes[0],'bold'))
            txt.tag_configure('label',font=('Segoe UI',sizes[0]+1,'bold'))
    ttk.Button(bar,text='A+  Larger',command=lambda:resize(1)).pack(side='right',padx=4)
    ttk.Button(bar,text='A−  Smaller',command=lambda:resize(-1)).pack(side='right',padx=4)

    nb=ttk.Notebook(container);nb.pack(fill='both',expand=True)
    for heading,body in HELP_SECTIONS:
        frame=ttk.Frame(nb,padding=(7,10))
        nb.add(frame,text=heading)
        content=tk.Frame(frame,bg='white',highlightthickness=1,highlightbackground='#e3edf2')
        content.pack(fill='both',expand=True)
        txt=tk.Text(content,wrap='word',font=('Segoe UI',sizes[0]),
                    bg='white',fg='#18384d',padx=25,pady=17,relief='flat',
                    insertbackground='#17344b',spacing1=3,spacing2=1,spacing3=7,
                    cursor='arrow')
        scroll=ttk.Scrollbar(content,orient='vertical',command=txt.yview)
        txt.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');txt.pack(side='left',fill='both',expand=True)
        txt.tag_configure('section',font=('Segoe UI',sizes[0]+2,'bold'),foreground='#0c6783',spacing1=8,spacing3=12)
        txt.tag_configure('label',font=('Segoe UI',sizes[0]+1,'bold'),foreground='#0b5d78',spacing1=8,spacing3=3)
        txt.tag_configure('step',font=('Segoe UI',sizes[0],'bold'),foreground='#123c55',lmargin1=6,lmargin2=12,spacing3=10)
        txt.tag_configure('body',foreground='#243e50',spacing2=2,spacing3=6)
        txt.tag_configure('detail',foreground='#435f71',lmargin1=22,lmargin2=22,spacing3=6)
        lines=body.splitlines()
        for ix,line in enumerate(lines):
            stripped=line.strip()
            if not stripped:
                txt.insert('end','\n');continue
            if ix==0 or (line==stripped and stripped.isupper()):
                tag='section'
            elif line.startswith('  '):
                tag='detail'
            elif stripped[:1].isdigit() and stripped[1:3] in ('. ',') '):
                tag='step'
            elif line==stripped and heading=='Every control':
                tag='label'
            else:
                tag='body'
            txt.insert('end',stripped+'\n',tag)
        txt.configure(state='disabled')
        text_widgets.append(txt)
    # Keep Notebook immediately inside container so MaritimeGUI.show_help('Program Arty A7') works.
    footer=ttk.Frame(container);footer.pack(fill='x',pady=(10,0))
    ttk.Label(footer,text='Physical FPGA test = COM port + correct bitstream + bit-exact FIR verification.',
              font=('Segoe UI',10)).pack(side='left')
    ttk.Button(footer,text='Close guide',command=w.destroy).pack(side='right')
    return w
