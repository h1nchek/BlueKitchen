"""Small cross-platform Tkinter interface for BlueKitchen."""

from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from bluekitchen import __version__
from bluekitchen.boot import inspect_boot_image
from bluekitchen.dynamic_partitions import inspect_super_image
from bluekitchen.extractor import extract_zip
from bluekitchen.image import expand_sparse_image, inspect_image
from bluekitchen.inspector import inspect_zip
from bluekitchen.payload import inspect_payload


OPERATIONS: dict[str, tuple[str, bool]] = {
    "Inspect ROM ZIP": ("zip", False),
    "Extract ROM ZIP": ("extract", True),
    "Inspect OTA payload": ("payload", False),
    "Inspect Android image": ("image", False),
    "Expand sparse image": ("expand", True),
    "Inspect boot / vendor_boot": ("boot", False),
    "Inspect super image": ("super", False),
}


class BlueKitchenApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"BlueKitchen {__version__}")
        self.root.geometry("900x650")
        self.root.minsize(680, 480)
        self.results: queue.Queue[tuple[bool, Any]] = queue.Queue()
        self.last_report: dict[str, Any] | None = None

        container = ttk.Frame(root, padding=14)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="BlueKitchen", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(
            container,
            text="Android ROM analysis and preparation tools",
        ).pack(anchor="w", pady=(0, 12))

        controls = ttk.LabelFrame(container, text="Operation", padding=10)
        controls.pack(fill="x")
        self.operation = tk.StringVar(value="Inspect ROM ZIP")
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()

        ttk.Label(controls, text="Task").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.operation_box = ttk.Combobox(
            controls, textvariable=self.operation, values=list(OPERATIONS), state="readonly"
        )
        self.operation_box.grid(row=0, column=1, columnspan=2, sticky="ew", pady=4)
        self.operation_box.bind("<<ComboboxSelected>>", self._update_output_visibility)

        ttk.Label(controls, text="Input file").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(controls, textvariable=self.input_path).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(controls, text="Browse…", command=self._browse_input).grid(row=1, column=2, padx=(8, 0))

        self.output_label = ttk.Label(controls, text="Output")
        self.output_entry = ttk.Entry(controls, textvariable=self.output_path)
        self.output_button = ttk.Button(controls, text="Choose…", command=self._browse_output)

        self.run_button = ttk.Button(controls, text="Run", command=self._run)
        self.run_button.grid(row=3, column=1, sticky="w", pady=(10, 0))
        self.save_button = ttk.Button(controls, text="Save report…", command=self._save_report)
        self.save_button.grid(row=3, column=2, sticky="e", padx=(8, 0), pady=(10, 0))
        controls.columnconfigure(1, weight=1)

        report_frame = ttk.LabelFrame(container, text="Report", padding=8)
        report_frame.pack(fill="both", expand=True, pady=(12, 0))
        self.report = tk.Text(report_frame, wrap="word", font=("Consolas", 10), state="disabled")
        scrollbar = ttk.Scrollbar(report_frame, orient="vertical", command=self.report.yview)
        self.report.configure(yscrollcommand=scrollbar.set)
        self.report.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.status = tk.StringVar(value="Ready")
        ttk.Label(container, textvariable=self.status).pack(anchor="w", pady=(8, 0))
        self._update_output_visibility()

    def _update_output_visibility(self, _event: object | None = None) -> None:
        _key, needs_output = OPERATIONS[self.operation.get()]
        if needs_output:
            self.output_label.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
            self.output_entry.grid(row=2, column=1, sticky="ew", pady=4)
            self.output_button.grid(row=2, column=2, padx=(8, 0))
        else:
            self.output_label.grid_remove()
            self.output_entry.grid_remove()
            self.output_button.grid_remove()

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(title="Choose Android firmware file")
        if path:
            self.input_path.set(path)
            if not self.output_path.get():
                source = Path(path)
                if OPERATIONS[self.operation.get()][0] == "extract":
                    self.output_path.set(str(source.with_suffix("")) + "-unpacked")
                elif OPERATIONS[self.operation.get()][0] == "expand":
                    self.output_path.set(str(source.with_suffix("")) + ".raw")

    def _browse_output(self) -> None:
        key, _needs_output = OPERATIONS[self.operation.get()]
        if key == "extract":
            path = filedialog.askdirectory(title="Choose a new output directory")
        else:
            path = filedialog.asksaveasfilename(title="Save expanded raw image")
        if path:
            self.output_path.set(path)

    def _set_report(self, value: str) -> None:
        self.report.configure(state="normal")
        self.report.delete("1.0", "end")
        self.report.insert("1.0", value)
        self.report.configure(state="disabled")

    def _run(self) -> None:
        source = self.input_path.get().strip()
        if not source:
            messagebox.showwarning("BlueKitchen", "Choose an input file first.")
            return
        if not Path(source).is_file():
            messagebox.showerror("BlueKitchen", "The selected input file does not exist.")
            return

        key, needs_output = OPERATIONS[self.operation.get()]
        destination = self.output_path.get().strip()
        if needs_output and not destination:
            messagebox.showwarning("BlueKitchen", "Choose an output path first.")
            return

        self.run_button.configure(state="disabled")
        self.status.set("Working…")
        self._set_report("Processing…")

        def worker() -> None:
            try:
                functions: dict[str, Callable[..., dict[str, Any]]] = {
                    "zip": inspect_zip,
                    "extract": extract_zip,
                    "payload": inspect_payload,
                    "image": inspect_image,
                    "expand": expand_sparse_image,
                    "boot": inspect_boot_image,
                    "super": inspect_super_image,
                }
                if needs_output:
                    result = functions[key](source, destination)
                else:
                    result = functions[key](source)
                self.results.put((True, result))
            except Exception as exc:  # show domain and filesystem errors in the report
                self.results.put((False, str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, self._poll_result)

    def _poll_result(self) -> None:
        try:
            success, payload = self.results.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll_result)
            return

        self.run_button.configure(state="normal")
        if success:
            self.last_report = payload
            self._set_report(json.dumps(payload, indent=2, ensure_ascii=False))
            self.status.set("Completed")
        else:
            self.last_report = None
            self._set_report(f"Operation failed\n\n{payload}")
            self.status.set("Failed")

    def _save_report(self) -> None:
        if self.last_report is None:
            messagebox.showinfo("BlueKitchen", "There is no successful report to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save JSON report",
            defaultextension=".json",
            filetypes=[("JSON report", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps(self.last_report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            self.status.set(f"Report saved: {path}")
        except OSError as exc:
            messagebox.showerror("BlueKitchen", f"Could not save report: {exc}")


def main() -> None:
    root = tk.Tk()
    BlueKitchenApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
