"""RevF UX and real-vs-estimated temperature evidence invariants."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'host'))
from engineering_summary import collect, read_xadc, to_markdown


def test_no_xadc_does_not_claim_a_measurement(tmp_path):
    d=read_xadc(tmp_path)
    assert d['status']=='NOT_MEASURED'
    assert d['latest_c'] is None
    s=collect(ROOT)
    # The local engineering bundle may now contain real operator XADC data.
    assert s['xadc']['status']==read_xadc(ROOT)['status']
    if s['xadc']['status']=='MEASURED':
        assert 'MEASURED' in to_markdown(s)
    else:
        assert 'NOT MEASURED' in to_markdown(s)


def test_reads_only_real_xadc_csv_records(tmp_path):
    path=tmp_path/'evidence/final_validation/xadc_snapshots.csv'
    path.parent.mkdir(parents=True)
    path.write_text('timestamp_local,phase,die_temperature_c,source\n'
                    '2026-11-23T12:00:00+0000,idle,28.5,Vivado_Hardware_Manager_XADC\n'
                    '2026-11-23T12:15:00+0000,after_workload,31.75,Vivado_Hardware_Manager_XADC\n'
                    '2026-11-23T12:16:00+0000,fiction,999,Vivado_Hardware_Manager_XADC\n'
                    '2026-11-23T12:17:00+0000,fake,44.2,Estimated_Vivado_Power_Report\n')
    d=read_xadc(tmp_path)
    assert d['status']=='MEASURED'
    assert d['latest_c']==31.75
    assert len(d['snapshots'])==2
    assert d['snapshots'][1]['phase']=='after_workload'


def test_duplicate_navigation_removed_and_audio_setting_visible():
    import tkinter as tk
    try:
        root=tk.Tk()
    except tk.TclError:
        import pytest
        pytest.skip('Display not available')
    try:
        from maritime_gui import MaritimeGUI
        gui=MaritimeGUI(root)
        root.update_idletasks()
        assert [gui.main_tabs.tab(i,'text') for i in range(gui.main_tabs.index('end'))]==[
            'Implementation','Video Assessment','Audio Assessment','Summary Report','Help']
        assert root.cget('menu') in ('',None)
        assert gui.tools_menu.index('end')>=4
        assert gui.cleanup_combo.get()=='Maritime adaptive'
        observed=read_xadc(ROOT)
        expect=(f"{observed['latest_c']:.1f}°C" if observed['status']=='MEASURED' else 'Not measured')
        assert gui.summary_tiles['Die temp (XADC)'].get()==expect
        assert 'FPGA die temperature using XADC' in gui._help_sections
    finally:
        root.destroy()
