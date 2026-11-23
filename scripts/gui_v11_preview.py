from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
import tkinter as tk
from PIL import ImageGrab
from maritime_gui import MaritimeGUI
from unified_pipeline import run_unified_pipeline
ROOT=Path(__file__).resolve().parents[1]
r=tk.Tk();r.geometry('1500x870');app=MaritimeGUI(r);r.update_idletasks();r.update()
res=run_unified_pipeline(ROOT/'videos/03_Unified_Quick_Test_3s.mp4',None,
                         ROOT/'build/gui_v11_preview',None,audio_cleanup='Maritime adaptive')
app.source=res.video
app._accept_result(res)
r.update_idletasks();r.update()
app.main_tabs.select(app.audio_assessment_tab);r.update_idletasks();r.update()
print('audio_plot_height',app.audiocanvas.get_tk_widget().winfo_height())
assert app.audiocanvas.get_tk_widget().winfo_height()>=500
print('label',app.audio_context.get(),app.audio_stage.get());assert 'HOST adaptive denoiser' in app.audio_stage.get()
ImageGrab.grab(bbox=(0,0,1500,870)).save('/mnt/data/Maritime_GUI_v1_1_audio_assessment.png')
app.main_tabs.select(app.assessment_tab);r.update_idletasks();r.update()
ImageGrab.grab(bbox=(0,0,1500,870)).save('/mnt/data/Maritime_GUI_v1_1_video_assessment.png')
app._close()
print('GUI_V11_PREVIEW_PASS')
