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
    tree.heading("Aktivite", text="Activity ID | Activity Name")
    tree.column("Aktivite", width=580)
    tree.pack(fill="both", expand=True)

    code_map = results["code_map"]
    name_map = results["name_map"]

    for tid in items:
        code = code_map.get(tid, "")
        name = name_map.get(tid, "")
        tree.insert("", "end", values=(f"{code} | {name}",))

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
    c.drawString(50, y, "XER Quality Checker Report")
    y -= 30

    c.setFont("Helvetica", 12)
    c.drawString(50, y, "Control Summary:")
    y -= 20

    summary = [
        f"FF + SS: {results['ff_ss_total']} / {int(results['ff_ss_limit'])}",
        f"SF: {results['sf']}",
        f"Lag: {results['lag']}",
        f"Open-Start: {len(results['open_start'])}",
        f"Open-Finish: {len(results['open_finish'])}",
        f">14 Days: {len(results['long_duration'])}",
        f"Float Limit Exceeded: {len(results['high_float'])}"
    ]

    for line in summary:
        c.drawString(70, y, "- " + line)
        y -= 20

    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Detailed Non-Compliant Activities:")
    y -= 20

    code_map = results["code_map"]
    name_map = results["name_map"]

    def write_list(title, items):
        nonlocal y
        c.setFont("Helvetica-Bold", 11)
        c.drawString(60, y, title)
        y -= 20
        c.setFont("Helvetica", 10)
        for tid in items:
            code = code_map.get(tid, "")
            name = name_map.get(tid, "")
            c.drawString(80, y, f"- {code} | {name}")
            y -= 15
            if y < 50:
                c.showPage()
                y = height - 50

    write_list("SF Relationships:", results["sf_list"])
    write_list("Activities with Lag:", results["lag_list"])
    write_list("Open-Start:", results["open_start"])
    write_list("Open-Finish:", results["open_finish"])
    write_list("Activities Longer Than 14 Days:", results["long_duration"])
    write_list("Activities Exceeding Float Limit:", results["high_float"])

    c.save()

def export_excel(results):
    path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel Files", "*.xlsx")]
    )
    if not path:
        return

    writer = pd.ExcelWriter(path, engine="xlsxwriter")

    code_map = results["code_map"]
    name_map = results["name_map"]

    def write_sheet(name, ids):
        df = pd.DataFrame({
            "Activity ID": [code_map.get(i, "") for i in ids],
            "Activity Name": [name_map.get(i, "") for i in ids],
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
    root.title("XER Quality Checker – Results")
    root.geometry("1100x900")
    root.configure(bg="#f0f4f7")

    tk.Label(root, text="Quality Check Results", font=("Arial", 22, "bold"), bg="#f0f4f7").pack(pady=15)

    tree = ttk.Treeview(root, columns=("Condition", "Status", "Description", "Report"), show="headings")
    tree.heading("Condition", text="Condition")
    tree.heading("Status", text="Status")
    tree.heading("Description", text="Description")
    tree.heading("Report", text="Report")

    tree.column("Condition", width=300)
    tree.column("Status", width=80)
    tree.column("Description", width=600)
    tree.column("Report", width=100)

    tree.pack(fill="both", expand=True)

    # --- FULL DESCRIPTION PANEL ---
    desc_label = tk.Label(root, text="Full Description:", font=("Arial", 14, "bold"), bg="#f0f4f7")
    desc_label.pack(pady=10)

    desc_box = tk.Text(root, height=8, wrap="word", font=("Arial", 12))
    desc_box.pack(fill="x", padx=20)

    def on_select(event):
        item = tree.selection()
        if item:
            desc = tree.item(item, "values")[2]
            desc_box.delete("1.0", tk.END)
            desc_box.insert(tk.END, desc)

    tree.bind("<<TreeviewSelect>>", on_select)

    # ---- ROWS (Conditions) ----
    if res["ff_ss_ok"]:
        desc = "FF and SS relationships are within the 20% limit."
        status = "✔"
    else:
        desc = (
            f"FF and SS relationships exceed the limit. "
            f"There are {res['ff_ss_total']} relationships total; "
            f"the maximum allowed is {int(res['ff_ss_limit'])}."
        )
        status = "❌"
    tree.insert("", "end", values=(
        "FF + SS Limit 20%",
        status,
        desc,
        "Detail"
    ))

    if res["sf"] == 0:
        desc = "No SF (Start-to-Finish) relationships were found in the schedule."
        status = "✔"
    else:
        desc = (
            f"{res['sf']} SF (Start-to-Finish) relationships were detected in the plan. "
            "SF relationships should not be used because they break logical flow."
        )
        status = "❌"
    tree.insert("", "end", values=(
        "SF relationship should not exist",
        status,
        desc,
        "Detail"
    ))

    if res["lag"] == 0:
        desc = "No lag usage was detected in any relationship."
        status = "✔"
    else:
        desc = (
            f"Lag usage was detected in {res['lag']} relationships. "
            "Lag usage should be kept to a minimum."
        )
        status = "❌"
    tree.insert("", "end", values=(
        "Lag usage should be minimal",
        status,
        desc,
        "Detail"
    ))

    if len(res["open_start"]) == 0:
        desc = "All activities have at least one predecessor (no Open-Start)."
        status = "✔"
    else:
        desc = (
            f"{len(res['open_start'])} activities do not have a predecessor (Open-Start). "
            "These should be reviewed as possible start nodes in the logical network."
        )
        status = "❌"
    tree.insert("", "end", values=(
        "Open-Start should not exist",
        status,
        desc,
        "Detail"
    ))

    if len(res["open_finish"]) == 0:
        desc = "All activities have at least one successor (no Open-Finish)."
        status = "✔"
    else:
        desc = (
            f"{len(res['open_finish'])} activities do not have a successor (Open-Finish). "
            "These should be reviewed as possible end nodes in the logical network."
        )
        status = "❌"
    tree.insert("", "end", values=(
        "Open-Finish should not exist",
        status,
        desc,
        "Detail"
    ))

    if len(res["long_duration"]) == 0:
        desc = "No activities are longer than 14 days."
        status = "✔"
    else:
        desc = (
            f"{len(res['long_duration'])} activities are longer than 14 days. "
            "Long-duration activities should be broken into smaller, more manageable segments."
        )
        status = "❌"
    tree.insert("", "end", values=(
        "Activity duration ≤ 14 days",
        status,
        desc,
        "Detail"
    ))

    if len(res["high_float"]) == 0:
        desc = "No activities exceed the 20% total float limit of the project duration."
        status = "✔"
    else:
        desc = (
            f"{len(res['high_float'])} activities exceed the 20% total float limit of the project duration. "
            "High float values may indicate that the schedule logic or critical path needs to be reviewed."
        )
        status = "❌"
    tree.insert("", "end", values=(
        "Float ≤ 20% limit",
        status,
        desc,
        "Detail"
    ))

    # ---- DOUBLE-CLICK REPORT HANDLER ----
    def on_double_click(event):
        item = tree.identify_row(event.y)
        if not item:
            return
        values = tree.item(item, "values")
        condition = values[0]

        if condition == "FF + SS Limit 20%":
            show_report("FF + SS Relationships", res["ff_list"] + res["ss_list"], res)
        elif condition == "SF relationship should not exist":
            show_report("SF Relationships", res["sf_list"], res)
        elif condition == "Lag usage should be minimal":
            show_report("Lagged Relationships", res["lag_list"], res)
        elif condition == "Open-Start should not exist":
            show_report("Open-Start Activities", res["open_start"], res)
        elif condition == "Open-Finish should not exist":
            show_report("Open-Finish Activities", res["open_finish"], res)
        elif condition == "Activity duration ≤ 14 days":
            show_report("Activities > 14 Days", res["long_duration"], res)
        elif condition == "Float ≤ 20% limit":
            show_report("Float Above 20% Limit", res["high_float"], res)

    tree.bind("<Double-1>", on_double_click)

    # ---- BUTTONS ----
    btn_frame = tk.Frame(root, bg="#f0f4f7")
    btn_frame.pack(pady=15)

    tk.Button(
        btn_frame,
        text="Export PDF",
        font=("Arial", 12, "bold"),
        command=lambda: export_pdf(res),
        bg="#4CAF50",
        fg="white",
        width=20
    ).pack(side="left", padx=10)

    tk.Button(
        btn_frame,
        text="Export Excel",
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

    tk.Label(root, text="Quality Criteria", font=("Arial", 18, "bold"), bg="#e8eef3").pack(pady=10)

    criteria = [
        "FF + SS relationships must not exceed 20% of total activities.",
        "No SF relationship should appear in the plan.",
        "Lag usage should be kept to a minimum.",
        "No Open‑Start activity should exist.",
        "No Open‑Finish activity should exist.",
        "Activity duration should not exceed 14 days.",
        "Total float should not exceed 20% of the project duration."
    ]

    tree = ttk.Treeview(root, columns=("Condition"), show="headings")
    tree.heading("Condition", text="Quality Criteria")
    tree.column("Condition", width=850)
    tree.pack(fill="both", expand=True)

    for item in criteria:
        tree.insert("", "end", values=(item,))

    def select_file():
        path = filedialog.askopenfilename(
            title="Select XER file",
            filetypes=[("XER Files", "*.xer"), ("All Files", "*.*")]
        )
        if path:
            xer = read_xer(path)
            results = analyze(xer)
            code_map, name_map = build_task_map(xer)
            results["code_map"] = code_map
            results["name_map"] = name_map
            show_second(results)

    tk.Button(
        root,
        text="Select XER File and Check",
        font=("Arial", 12, "bold"),
        command=select_file,
        bg="#4CAF50",
        fg="white",
        width=25
    ).pack(pady=20)

    root.mainloop()

if __name__ == "__main__":
    show_first()
