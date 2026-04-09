from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .core import CoreService
from .desktop_state import DesktopAppState, DesktopController


class DesktopShell:
    def __init__(self, state_path: str | Path) -> None:
        self.core = CoreService(state_path=state_path)
        self.state = DesktopAppState(self.core)
        self.controller = DesktopController(self.core, self.state)
        self.root = tk.Tk()
        self.root.title("Hybrid Transfer")
        self.root.geometry("1080x720")
        self.status_var = tk.StringVar(value="Ready")
        self.access_var = tk.StringVar(value="")
        self.settings_vars: dict[str, tk.Variable] = {}
        self._pending_guest_token: str | None = None
        self.device_list: tk.Listbox
        self.pending_guest_list: tk.Listbox
        self.task_tree: ttk.Treeview
        self.history_list: tk.Listbox
        self.drop_text: tk.Text
        self._build_layout()
        self._refresh_all()
        self.root.after(1000, self._poll)

    def _build_layout(self) -> None:
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=12, pady=12)
        ttk.Button(toolbar, text="Add Manual Device", command=self._add_manual_device).pack(side="left")
        ttk.Button(toolbar, text="Pair Selected", command=self._pair_selected_device).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Send Files", command=self._choose_files).pack(side="left")
        ttk.Button(toolbar, text="Send Folder", command=self._choose_folder).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_all).pack(side="left")

        access = ttk.LabelFrame(self.root, text="LAN Access")
        access.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Label(
            access,
            textvariable=self.access_var,
            justify="left",
        ).pack(fill="x", padx=8, pady=8)

        guest_access = ttk.LabelFrame(self.root, text="Pending Browser Access")
        guest_access.pack(fill="x", padx=12, pady=(0, 12))
        guest_controls = ttk.Frame(guest_access)
        guest_controls.pack(fill="x", padx=8, pady=8)
        self.pending_guest_list = tk.Listbox(guest_controls, exportselection=False, height=4)
        self.pending_guest_list.pack(side="left", fill="both", expand=True)
        self.pending_guest_list.bind("<<ListboxSelect>>", self._on_pending_guest_selected)
        ttk.Button(guest_controls, text="Approve Selected Browser", command=self._approve_selected_guest).pack(
            side="left", padx=(8, 0)
        )

        content = ttk.Frame(self.root)
        content.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        content.columnconfigure(0, weight=2)
        content.columnconfigure(1, weight=3)
        content.rowconfigure(0, weight=3)
        content.rowconfigure(1, weight=2)

        devices = ttk.LabelFrame(content, text="Devices")
        devices.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        self.device_list = tk.Listbox(devices, exportselection=False)
        self.device_list.pack(fill="both", expand=True, padx=8, pady=8)
        self.device_list.bind("<<ListboxSelect>>", self._on_device_selected)

        tasks = ttk.LabelFrame(content, text="Active Tasks")
        tasks.grid(row=0, column=1, sticky="nsew", pady=(0, 8))
        self.task_tree = ttk.Treeview(tasks, columns=("peer", "state", "progress", "items"), show="headings", height=10)
        for column, label in [("peer", "Peer"), ("state", "State"), ("progress", "Progress"), ("items", "Items")]:
            self.task_tree.heading(column, text=label)
        self.task_tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(tasks, text="Retry Selected Task", command=self._retry_selected_task).pack(anchor="e", padx=8, pady=(0, 8))

        history = ttk.LabelFrame(content, text="History")
        history.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.history_list = tk.Listbox(history)
        self.history_list.pack(fill="both", expand=True, padx=8, pady=8)

        settings = ttk.LabelFrame(content, text="Settings")
        settings.grid(row=1, column=1, sticky="nsew")
        self._build_settings(settings)

        drop = ttk.LabelFrame(self.root, text="Drop Workflow")
        drop.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Label(drop, text="Paste newline-separated file paths and click send to selected device.").pack(anchor="w", padx=8, pady=(8, 0))
        self.drop_text = tk.Text(drop, height=4)
        self.drop_text.pack(fill="x", padx=8, pady=8)
        ttk.Button(drop, text="Send Dropped Paths", command=self._send_drop_payload).pack(anchor="e", padx=8, pady=(0, 8))

        ttk.Label(self.root, textvariable=self.status_var).pack(fill="x", padx=12, pady=(0, 8))

    def _build_settings(self, parent: ttk.LabelFrame) -> None:
        current = self.core.get_settings()
        self.settings_vars["shared_dir"] = tk.StringVar(value=current["shared_dir"])
        self.settings_vars["default_conflict_policy"] = tk.StringVar(value=current["default_conflict_policy"])
        self.settings_vars["auto_accept_trusted"] = tk.BooleanVar(value=current["auto_accept_trusted"])

        ttk.Label(parent, text="Shared Dir").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(parent, textvariable=self.settings_vars["shared_dir"]).grid(row=0, column=1, sticky="ew", padx=8, pady=8)
        ttk.Label(parent, text="Conflict Policy").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ttk.Combobox(
            parent,
            textvariable=self.settings_vars["default_conflict_policy"],
            values=["overwrite", "skip", "rename"],
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", padx=8, pady=8)
        ttk.Checkbutton(parent, text="Auto-accept trusted peers", variable=self.settings_vars["auto_accept_trusted"]).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=8, pady=8
        )
        ttk.Button(parent, text="Save Settings", command=self._save_settings).grid(row=3, column=1, sticky="e", padx=8, pady=8)
        parent.columnconfigure(1, weight=1)

    def _add_manual_device(self) -> None:
        address = simpledialog.askstring("Manual Device", "Address:")
        if not address:
            return
        name = simpledialog.askstring("Manual Device", "Device name:", initialvalue=address) or address
        try:
            self.controller.add_manual_device(name=name, address=address, port=self.core.get_settings()["manual_port"])
        except ValueError as exc:
            messagebox.showerror("Hybrid Transfer", str(exc))
            return
        self.status_var.set("Manual device added.")
        self._refresh_all()

    def _pair_selected_device(self) -> None:
        device = self._selected_device()
        if not device:
            messagebox.showerror("Hybrid Transfer", "Select a device first.")
            return
        request = self.core.start_pairing(device["device_id"], device["name"])
        messagebox.showinfo("Pair Device", f"Pairing code for {device['name']}: {request['pairing_code']}")

    def _choose_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Select files")
        if paths:
            self._send_paths([Path(path) for path in paths])

    def _choose_folder(self) -> None:
        path = filedialog.askdirectory(title="Select folder")
        if path:
            self._send_paths([Path(path)])

    def _send_paths(self, paths: list[Path]) -> None:
        try:
            self.controller.send_paths(paths)
            self.status_var.set("Transfer started.")
        except Exception as exc:
            messagebox.showerror("Hybrid Transfer", str(exc))
            self.status_var.set(str(exc))
        self._refresh_all()

    def _send_drop_payload(self) -> None:
        try:
            self.controller.handle_drop(self.drop_text.get("1.0", tk.END))
            self.status_var.set("Dropped paths sent.")
        except Exception as exc:
            messagebox.showerror("Hybrid Transfer", str(exc))
            self.status_var.set(str(exc))
        self._refresh_all()

    def _save_settings(self) -> None:
        try:
            self.controller.update_settings(
                shared_dir=self.settings_vars["shared_dir"].get(),
                default_conflict_policy=self.settings_vars["default_conflict_policy"].get(),
                auto_accept_trusted=self.settings_vars["auto_accept_trusted"].get(),
            )
            self.status_var.set("Settings saved.")
        except Exception as exc:
            messagebox.showerror("Hybrid Transfer", str(exc))
            self.status_var.set(str(exc))

    def _retry_selected_task(self) -> None:
        selection = self.task_tree.selection()
        if not selection:
            messagebox.showerror("Hybrid Transfer", "Select a task first.")
            return
        task_id = selection[0]
        try:
            self.controller.retry_task(task_id)
            self.status_var.set("Retry started.")
        except Exception as exc:
            messagebox.showerror("Hybrid Transfer", str(exc))
            self.status_var.set(str(exc))
        self._refresh_all()

    def _approve_selected_guest(self) -> None:
        snapshot = self.state.snapshot()
        session = None
        selection = self.pending_guest_list.curselection()
        if selection:
            session = snapshot.pending_guest_sessions[selection[0]]
        elif self._pending_guest_token:
            session = next(
                (
                    pending
                    for pending in snapshot.pending_guest_sessions
                    if pending["token"] == self._pending_guest_token
                ),
                None,
            )
        if session is None:
            messagebox.showerror("Hybrid Transfer", "Select a browser session first.")
            return
        try:
            self.controller.approve_guest_session(session["token"])
            self._pending_guest_token = None
            self.status_var.set(f"Approved browser access for {session['guest_id']}.")
        except Exception as exc:
            messagebox.showerror("Hybrid Transfer", str(exc))
            self.status_var.set(str(exc))
        self._refresh_all()

    def _on_device_selected(self, _event=None) -> None:
        device = self._selected_device()
        if not device:
            return
        self.controller.select_device(device["device_id"])
        self.status_var.set(f"Selected {device['name']}")

    def _selected_device(self) -> dict[str, Any] | None:
        selection = self.device_list.curselection()
        if not selection:
            return None
        return self.state.snapshot().devices[selection[0]]

    def _selected_pending_guest_token(self) -> str | None:
        selection = self.pending_guest_list.curselection()
        if not selection:
            return None
        label = self.pending_guest_list.get(selection[0])
        if "[" not in label or not label.endswith("]"):
            return None
        return label.rsplit("[", 1)[1][:-1]

    def _on_pending_guest_selected(self, _event=None) -> None:
        self._pending_guest_token = self._selected_pending_guest_token()

    def _refresh_pending_guest_list(self, snapshot) -> None:
        selected_token = self._pending_guest_token or self._selected_pending_guest_token()
        selected_index = None

        self.pending_guest_list.delete(0, tk.END)
        for index, session in enumerate(snapshot.pending_guest_sessions):
            self.pending_guest_list.insert(tk.END, f"{session['guest_id']} [{session['token']}]")
            if session["token"] == selected_token:
                selected_index = index

        if selected_index is not None:
            self.pending_guest_list.selection_set(selected_index)
            self._pending_guest_token = selected_token
        else:
            self._pending_guest_token = None

    def _refresh_all(self) -> None:
        snapshot = self.state.snapshot()

        self.device_list.delete(0, tk.END)
        for device in snapshot.devices:
            trusted = "trusted" if self.core.trust.is_trusted(device["device_id"]) else "untrusted"
            self.device_list.insert(tk.END, f"{device['name']} [{device['address']}:{device['port']}] ({trusted})")

        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        for task in snapshot.active_tasks:
            self.task_tree.insert("", tk.END, iid=task["id"], values=(task["peer_id"], task["state"], task["progress"], task["item_count"]))

        self.history_list.delete(0, tk.END)
        for entry in snapshot.history:
            self.history_list.insert(tk.END, f"{entry['task_id']} - {entry['state']}")

        self._refresh_pending_guest_list(snapshot)

        lines = [f"Bind host: {snapshot.access_endpoints['bind_host']}"]
        for endpoint in snapshot.access_endpoints["addresses"]:
            lines.append(
                f"{endpoint['label']}: web {endpoint['web_url']} | transfer {endpoint['transfer_target']}"
            )
        self.access_var.set("\n".join(lines))

        for offer in snapshot.pending_offers:
            self._show_incoming_offer_dialog(offer)

    def _show_incoming_offer_dialog(self, offer: dict[str, Any]) -> None:
        conflict_policy = simpledialog.askstring(
            "Incoming Transfer",
            f"Incoming task from {offer['peer_id']} with {offer['file_count']} files.\n"
            f"Conflict policy (overwrite/skip/rename):",
            initialvalue=offer["conflict_policy"],
        )
        if conflict_policy is None:
            self.controller.reject_incoming(offer["offer_id"])
            self.status_var.set("Incoming transfer rejected.")
            return
        self.controller.accept_incoming(offer["offer_id"], conflict_policy=conflict_policy)
        self.status_var.set("Incoming transfer accepted.")

    def _poll(self) -> None:
        self._refresh_all()
        self.root.after(1000, self._poll)

    def run(self) -> None:
        self.root.mainloop()
