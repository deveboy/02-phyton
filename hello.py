import tkinter as tk
from tkinter import filedialog, ttk
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import pandas as pd

def safe_int(v, d=0):
    try:
        return int(float(v))
    except:
        return d

def safe_float(v, d=0.0):
    try:
        return float(v)
    except:
        return d

def read_xer(path):
    tables = {}
    current = None
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("%T"):
                current = line[2:].strip()
                tables[current] = []
                continue
            if current and line.startswith("%F"):
                tables[current + "_F"] = line[2:].split("\t")
                continue
            if current and line.startswith("%R"):
                tables[current].append(line.split("\t"))
    return tables

# TASK tablosundan: internal task id → task code, task name
def build_task_map(xer):
    TASK = xer.get("TASK", [])
    id_to_code = {}
    id_to_name = {}
    for t in TASK:
        tid = safe_int(t[1])
        task_code = t[14] if len(t) > 14 else ""
        task_name = t[15] if len(t) > 15 else ""
        id_to_code[tid] = task_code
        id_to_name[tid] = task_name
    return id_to_code, id_to_name

def map_task_columns(cols):
    colmap = {}

    duration_keys = [
        "orig_dur", "remain_dur", "target_dur", "act_dur",
        "duration", "recalc_dur", "at_complete_dur",
        "remain_work_qty", "target_work_qty", "act_work_qty",
        "remain_drtn_hr_cnt", "target_drtn_hr_cnt"
    ]

    float_keys = [
        "total_float_hr_cnt",
        "total_float", "float", "free_float",
        "remaining_float", "late_float",
        "float_hr_cnt", "float_day_cnt"
    ]

    start_keys = [
        "start_date", "early_start", "late_start",
        "act_start_date", "target_start_date"
    ]

    finish_keys = [
        "finish_date", "early_end_date", "late_end_date",
        "act_end_date", "target_end_date"
    ]

    for key in duration_keys:
        for i, c in enumerate(cols):
            if c.lower() == key:
                colmap["duration"] = i + 1
                break

    for key in float_keys:
        for i, c in enumerate(cols):
            if c.lower() == key:
                colmap["float"] = i + 1
                break

    for key in start_keys:
        for i, c in enumerate(cols):
            if c.lower() == key:
                colmap["start"] = i + 1
                break

    for key in finish_keys:
        for i, c in enumerate(cols):
            if c.lower() == key:
                colmap["finish"] = i + 1
                break

    return colmap

def analyze(xer):

    TASK = xer.get("TASK", [])
    PRED = xer.get("TASKPRED", [])
    TASK_F = xer.get("TASK_F", [])

    colmap = map_task_columns(TASK_F)

    duration_col = colmap.get("duration")
    float_col = colmap.get("float")
    start_col = colmap.get("start")
    finish_col = colmap.get("finish")

    durations = {}
    floats = {}
    starts = []
    finishes = []

    for t in TASK:
        tid = safe_int(t[1])

        if duration_col and duration_col < len(t):
            durations[tid] = safe_float(t[duration_col])

        if float_col and float_col < len(t):
            floats[tid] = safe_float(t[float_col])

        if start_col and start_col < len(t):
            starts.append(safe_float(t[start_col]))

        if finish_col and finish_col < len(t):
            finishes.append(safe_float(t[finish_col]))

    if starts and finishes:
        project_duration = max(finishes) - min(starts)
    else:
        project_duration = max(durations.values()) if durations else 0

    float_limit = project_duration * 0.20

    ff = ss = sf = 0
    lag_count = 0

    pred_ids = set()
    succ_ids = set()

    ff_list = []
    ss_list = []
    sf_list = []
    lag_list = []

    for p in PRED:
        if len(p) < 8:
            continue

        task_id = safe_int(p[2])
        pred_task_id = safe_int(p[3])
        pred_type = p[6]
        lag = safe_int(p[7])

        pred_ids.add(pred_task_id)
        succ_ids.add(task_id)

        if pred_type == "PR_FF":
            ff += 1
            ff_list.append(task_id)
        elif pred_type == "PR_SS":
            ss += 1
            ss_list.append(task_id)
        elif pred_type == "PR_SF":
            sf += 1
            sf_list.append(task_id)

        if lag > 0:
            lag_count += 1
            lag_list.append(task_id)

    task_ids = list(durations.keys())

    open_start = [tid for tid in task_ids if tid not in pred_ids]
    open_finish = [tid for tid in task_ids if tid not in succ_ids]

    long_duration = [tid for tid, d in durations.items() if d > 14]
    high_float = [tid for tid, fl in floats.items() if fl > float_limit]

    ff_ss_total = ff + ss
    ff_ss_limit = len(task_ids) * 0.20
    ff_ss_ok = ff_ss_total <= ff_ss_limit

    return {
        "ff": ff,
        "ss": ss,
        "sf": sf,
        "lag": lag_count,
        "open_start": open_start,
        "open_finish": open_finish,
        "long_duration": long_duration,
        "high_float": high_float,
        "ff_list": ff_list,
        "ss_list": ss_list,
        "sf_list": sf_list,
        "lag_list": lag_list,
        "ff_ss_total": ff_ss_total,
        "ff_ss_limit": ff_ss_limit,
        "ff_ss_ok": ff_ss_ok
    }

def show_report(title, items, results):
    win = tk.Toplevel()
    win.title(title)
    win.geometry("600x500")

    tree = ttk.Treeview(win, columns=("Aktivite"), show="headings")
    tree.heading("Aktivite", text="Task ID | Task Code | Task Name")
    tree.column("Aktivite", width=580)
    tree.pack(fill="both", expand=True)

    code_map = results.get("code_map", {})
    name_map = results.get("name_map", {})

    for tid in items:
        code = code_map.get(tid, "")
        name = name_map.get(tid, "")
        tree.insert("", "end", values=(f"{tid} | {code} | {name}",))

def export_pdf(results):
    path = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF Files", "*.pdf")]
    )
    if not path:
        return

    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "XER Quality Checker Raporu")
    y -= 30

    c.setFont("Helvetica", 12)
    c.drawString(50, y, "Kontrol Özeti:")
    y -= 20

    summary = [
        f"FF + SS: {results['ff_ss_total']} / {int(results['ff_ss_limit'])}",
        f"SF: {results['sf']}",
        f"Lag: {results['lag']}",
        f"Open-Start: {len(results['open_start'])}",
        f"Open-Finish: {len(results['open_finish'])}",
        f">14 Gün: {len(results['long_duration'])}",
        f"Float Limit Aşımı: {len(results['high_float'])}"
    ]

    for line in summary:
        c.drawString(70, y, "- " + line)
        y -= 20

    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Detaylı Uymayan Aktiviteler:")
    y -= 20

    code_map = results.get("code_map", {})
    name_map = results.get("name_map", {})

    def write_list(title, items):
        nonlocal y
        c.setFont("Helvetica-Bold", 11)
        c.drawString(60, y, title)
        y -= 20
        c.setFont("Helvetica", 10)
        for tid in items:
            code = code_map.get(tid, "")
            name = name_map.get(tid, "")
            c.drawString(80, y, f"- {tid} | {code} | {name}")
            y -= 15
            if y < 50:
                c.showPage()
                y = height - 50

    write_list("SF İlişkileri:", results["sf_list"])
    write_list("Lag İçeren Aktiviteler:", results["lag_list"])
    write_list("Open-Start:", results["open_start"])
    write_list("Open-Finish:", results["open_finish"])
    write_list("14 Günden Uzun Aktiviteler:", results["long_duration"])
    write_list("Float Limitini Aşan Aktiviteler:", results["high_float"])

    c.save()

def export_excel(results):
    path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel Files", "*.xlsx")]
    )
    if not path:
        return

    writer = pd.ExcelWriter(path, engine="xlsxwriter")

    code_map = results.get("code_map", {})
    name_map = results.get("name_map", {})

    def write_sheet(name, ids):
        df = pd.DataFrame({
            "Task ID": ids,
            "Task Code": [code_map.get(i, "") for i in ids],
            "Task Name": [name_map.get(i, "") for i in ids],
        })
        df.to_excel(writer, sheet_name=name, index=False)

    write_sheet("FF_SS", results["ff_list"] + results["ss_list"])
    write_sheet("SF", results["sf_list"])
    write_sheet("Lag", results["lag_list"])
    write_sheet("OpenStart", results["open_start"])
    write_sheet("OpenFinish", results["open_finish"])
    write_sheet("LongDuration", results["long_duration"])
    write_sheet("HighFloat", results["high_float"])

    writer.close()

def show_second(res):
    root = tk.Tk()
    root.title("XER Quality Checker – Sonuçlar")
    root.geometry("1100x750")
    root.configure(bg="#f0f4f7")

    tk.Label(root, text="Kontrol Sonuçları", font=("Arial", 22, "bold"), bg="#f0f4f7").pack(pady=15)

    tree = ttk.Treeview(root, columns=("Şart", "Durum", "Açıklama", "Rapor"), show="headings")
    tree.heading("Şart", text="Şart")
    tree.heading("Durum", text="Durum")
    tree.heading("Açıklama", text="Açıklama")
    tree.heading("Rapor", text="Rapor")

    tree.column("Şart", width=300)
    tree.column("Durum", width=80)
    tree.column("Açıklama", width=600)
    tree.column("Rapor", width=100)

    tree.pack(fill="both", expand=True)

    if res["ff_ss_ok"]:
        aciklama = "FF ve SS ilişkileri toplam aktivite sayısının %20 sınırı içinde."
    else:
        aciklama = (
            f"FF ve SS ilişkileri limitin üzerinde. Toplam {res['ff_ss_total']} ilişki var; "
            f"izin verilen üst sınır {int(res['ff_ss_limit'])}."
        )
    tree.insert("", "end", values=(
        "FF + SS Limit %20",
        "✔" if res["ff_ss_ok"] else "❌",
        aciklama,
        "Detay"
    ))

    if res["sf"] == 0:
        aciklama = "Plan içerisinde SF (Start-to-Finish) ilişkisi bulunmamaktadır."
    else:
        aciklama = (
            f"Plan içerisinde {res['sf']} adet SF (Start-to-Finish) ilişkisi tespit edilmiştir. "
            "SF ilişkisi mantıksal akışın geriye bağlanmasına neden olduğu için kullanılmamalıdır."
        )
    tree.insert("", "end", values=(
        "SF ilişkisi olmamalı",
        "✔" if res["sf"] == 0 else "❌",
        aciklama,
        "Detay"
    ))

    if res["lag"] == 0:
        aciklama = "Hiçbir ilişkide lag kullanılmamıştır."
    else:
        aciklama = (
            f"{res['lag']} adet ilişkide lag kullanımı tespit edilmiştir. "
            "Lag kullanımı minimum seviyede tutulmalıdır."
        )
    tree.insert("", "end", values=(
        "Lag kullanımı minimum olmalı",
        "✔" if res["lag"] == 0 else "❌",
        aciklama,
        "Detay"
    ))

    if len(res["open_start"]) == 0:
        aciklama = "Tüm aktivitelerin en az bir predecessor'ı bulunmaktadır."
    else:
        aciklama = (
            f"{len(res['open_start'])} aktivitenin predecessor'ı bulunmamaktadır (Open-Start). "
            "Bu aktiviteler mantıksal ağ içinde başlangıç noktası olarak kontrol edilmelidir."
        )
    tree.insert("", "end", values=(
        "Open‑Start olmamalı",
        "✔" if len(res["open_start"]) == 0 else "❌",
        aciklama,
        "Detay"
    ))

    if len(res["open_finish"]) == 0:
        aciklama = "Tüm aktivitelerin en az bir successor'ı bulunmaktadır."
    else:
        aciklama = (
            f"{len(res['open_finish'])} aktivitenin successor'ı bulunmamaktadır (Open-Finish). "
            "Bu aktiviteler mantıksal ağ içinde bitiş noktası olarak kontrol edilmelidir."
        )
    tree.insert("", "end", values=(
        "Open‑Finish olmamalı",
        "✔" if len(res["open_finish"]) == 0 else "❌",
        aciklama,
        "Detay"
    ))

    if len(res["long_duration"]) == 0:
        aciklama = "Hiçbir aktivitenin süresi 14 günü aşmamaktadır."
    else:
        aciklama = (
            f"{len(res['long_duration'])} aktivitenin süresi 14 günden uzundur. "
            "Uzun süreli aktiviteler, daha küçük ve yönetilebilir parçalara bölünmelidir."
        )
    tree.insert("", "end", values=(
        "Aktivite süresi ≤ 14 gün",
        "✔" if len(res["long_duration"]) == 0 else "❌",
        aciklama,
        "Detay"
    ))

    if len(res["high_float"]) == 0:
        aciklama = "Hiçbir aktivitenin total float değeri proje süresinin %20’sini aşmamaktadır."
    else:
        aciklama = (
            f"{len(res["high_float"])} aktivitenin total float değeri proje süresinin %20 limitini aşmaktadır. "
            "Yüksek float değerleri, ağ mantığının ve kritik yolun yeniden gözden geçirilmesini gerektirir."
        )
    tree.insert("", "end", values=(
        "Float ≤ %20 limit",
        "✔" if len(res["high_float"]) == 0 else "❌",
        aciklama,
        "Detay"
    ))

    def on_click(event):
        item = tree.identify_row(event.y)
        if not item:
            return
        values = tree.item(item, "values")
        şart = values[0]

        if şart == "FF + SS Limit %20":
            show_report("FF + SS İlişkileri", res["ff_list"] + res["ss_list"], res)
        elif şart == "SF ilişkisi olmamalı":
            show_report("SF İlişkileri", res["sf_list"], res)
        elif şart == "Lag kullanımı minimum olmalı":
            show_report("Lag İçeren Aktiviteler", res["lag_list"], res)
        elif şart == "Open‑Start olmamalı":
            show_report("Open‑Start Aktiviteleri", res["open_start"], res)
        elif şart == "Open‑Finish olmamalı":
            show_report("Open‑Finish Aktiviteleri", res["open_finish"], res)
        elif şart == "Aktivite süresi ≤ 14 gün":
            show_report("14 Günden Uzun Aktiviteler", res["long_duration"], res)
        elif şart == "Float ≤ %20 limit":
            show_report("Float Limitini Aşan Aktiviteler", res["high_float"], res)

    tree.bind("<Double-1>", on_click)

    btn_frame = tk.Frame(root, bg="#f0f4f7")
    btn_frame.pack(pady=15)

    tk.Button(
        btn_frame,
        text="PDF Olarak Kaydet",
        font=("Arial", 12, "bold"),
        command=lambda: export_pdf(res),
        bg="#4CAF50",
        fg="white",
        width=20
    ).pack(side="left", padx=10)

    tk.Button(
        btn_frame,
        text="Excel'e Aktar",
        font=("Arial", 12, "bold"),
        command=lambda: export_excel(res),
        bg="#2196F3",
        fg="white",
        width=20
    ).pack(side="left", padx=10)

    root.mainloop()

def show_first():
    root = tk.Tk()
    root.title("XER Quality Checker")
    root.geometry("900x600")
    root.configure(bg="#e8eef3")

    tk.Label(root, text="XER Quality Checker", font=("Arial", 26, "bold"), bg="#e8eef3").pack(pady=20)

    tk.Label(root, text="Kalite Şartları", font=("Arial", 18, "bold"), bg="#e8eef3").pack(pady=10)

    şartlar = [
        "FF + SS ilişkileri toplam aktivite sayısının %20’sini aşmamalıdır.",
        "SF ilişkisi plan içerisinde bulunmamalıdır.",
        "Lag kullanımı minimum seviyede olmalıdır.",
        "Open‑Start aktivitesi bulunmamalıdır.",
        "Open‑Finish aktivitesi bulunmamalıdır.",
        "Aktivite süresi 14 günü aşmamalıdır.",
        "Total float proje süresinin %20’sini aşmamalıdır."
    ]

    tree = ttk.Treeview(root, columns=("Şart"), show="headings")
    tree.heading("Şart", text="Kalite Şartları")
    tree.column("Şart", width=850)
    tree.pack(fill="both", expand=True)

    for s in şartlar:
        tree.insert("", "end", values=(s,))

    def select_file():
        path = filedialog.askopenfilename(
            title="XER dosyasını seç",
            filetypes=[("XER Files", "*.xer"), ("All Files", "*.*")]
        )
        if path:
            xer = read_xer(path)
            results = analyze(xer)

            # analyze SONRASI EK ADIM: VLOOKUP map’leri ekle
            code_map, name_map = build_task_map(xer)
            results["code_map"] = code_map
            results["name_map"] = name_map

            show_second(results)

    tk.Button(
        root,
        text="XER Dosyası Seç ve Kontrol Et",
        font=("Arial", 12, "bold"),
        command=select_file,
        bg="#4CAF50",
        fg="white",
        width=25
    ).pack(pady=20)

    root.mainloop()

if __name__ == "__main__":
    show_first()
