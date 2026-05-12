#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
import subprocess
import threading

class PackageRow(Gtk.ListBoxRow):
    def __init__(self, name, description, pkg_type):
        super().__init__()
        self.pkg_name = name
        self.pkg_type = pkg_type
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_margin_top(3)
        box.set_margin_bottom(3)
        self.check = Gtk.CheckButton()
        box.pack_start(self.check, False, False, 0)
        name_label = Gtk.Label(label=name, xalign=0)
        name_label.set_markup(f"<b>{GLib.markup_escape_text(name)}</b>")
        name_label.set_width_chars(30)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        box.pack_start(name_label, False, False, 0)
        desc_label = Gtk.Label(label=description, xalign=0)
        desc_label.set_ellipsize(Pango.EllipsizeMode.END)
        box.pack_start(desc_label, True, True, 0)
        self.add(box)

class PackageRemover(Gtk.Window):
    def __init__(self):
        super().__init__(title="Package Remover")
        self.set_default_size(750, 550)
        self.connect("destroy", Gtk.main_quit)

        self.packages = []
        self._password_cached = False

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add(vbox)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.set_margin_top(6)
        toolbar.set_margin_start(6)
        toolbar.set_margin_end(6)
        vbox.pack_start(toolbar, False, False, 0)

        self.select_all_btn = Gtk.Button(label="Selektuj sve")
        self.select_all_btn.connect("clicked", self.on_select_all)
        toolbar.pack_start(self.select_all_btn, False, False, 0)

        self.deselect_all_btn = Gtk.Button(label="Poništi sve")
        self.deselect_all_btn.connect("clicked", self.on_deselect_all)
        toolbar.pack_start(self.deselect_all_btn, False, False, 0)

        self.refresh_btn = Gtk.Button(label="Osveži")
        self.refresh_btn.connect("clicked", self.on_refresh)
        toolbar.pack_end(self.refresh_btn, False, False, 0)

        self.status_label = Gtk.Label(label="Učitavanje paketa...")
        toolbar.pack_end(self.status_label, False, False, 0)

        self.notebook = Gtk.Notebook()
        vbox.pack_start(self.notebook, True, True, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.set_margin_start(6)
        btn_box.set_margin_end(6)
        btn_box.set_margin_bottom(6)
        vbox.pack_start(btn_box, False, False, 0)

        self.uninstall_btn = Gtk.Button(label="Deinstaliraj selektovane")
        self.uninstall_btn.connect("clicked", self.on_uninstall)
        btn_box.pack_start(self.uninstall_btn, False, False, 0)

        self.uninstall_btn.set_sensitive(False)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        btn_box.pack_start(self.progress, True, True, 0)

        self.terminal_revealer = Gtk.Revealer()
        self.terminal_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        term_frame = Gtk.Frame(label="Izvršavanje")
        self.terminal_view = Gtk.TextView()
        self.terminal_view.set_editable(False)
        self.terminal_view.set_cursor_visible(False)
        self.terminal_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.terminal_view.set_size_request(-1, 120)
        self.terminal_buffer = self.terminal_view.get_buffer()
        scrolled_term = Gtk.ScrolledWindow()
        scrolled_term.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_term.add(self.terminal_view)
        term_frame.add(scrolled_term)
        self.terminal_revealer.add(term_frame)
        vbox.pack_start(self.terminal_revealer, False, False, 0)

        self._show_loading()

        self.load_packages()

    def _show_loading(self):
        while self.notebook.get_n_pages() > 0:
            self.notebook.remove_page(0)
        label = Gtk.Label(label="Učitavanje paketa...")
        self.notebook.append_page(Gtk.Box(), label)

    def create_tab(self, title):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.add(listbox)
        label = Gtk.Label(label=title)
        self.notebook.append_page(scrolled, label)
        return listbox

    def load_packages(self):
        self.status_label.set_text("Učitavanje paketa...")
        self.progress.set_fraction(0.0)
        self.progress.set_text("Učitavanje...")
        self.progress.set_show_text(True)
        thread = threading.Thread(target=self._load_all_packages, daemon=True)
        thread.start()

    def _load_all_packages(self):
        apt_pkgs = []
        snap_pkgs = []
        flatpak_pkgs = []
        self._error_log = []
        try:
            apt_pkgs = self._get_apt_packages()
        except Exception as e:
            self._error_log.append(f"⚠️ Greška kod apt-a: {e}")
        try:
            snap_pkgs = self._get_snap_packages()
        except Exception as e:
            self._error_log.append(f"⚠️ Greška kod snap-a: {e}")
        try:
            flatpak_pkgs = self._get_flatpak_packages()
        except Exception as e:
            self._error_log.append(f"⚠️ Greška kod flatpak-a: {e}")
        GLib.idle_add(self._populate_tabs, apt_pkgs, snap_pkgs, flatpak_pkgs)

    def _get_apt_packages(self):
        result = subprocess.run(
            ["apt", "list", "--installed"],
            capture_output=True, text=True, timeout=60
        )
        lines = result.stdout.strip().split("\n")
        pkgs = []
        for line in lines:
            if "/" not in line:
                continue
            parts = line.split()
            name = parts[0].split("/")[0]
            ver = parts[1] if len(parts) > 1 else ""
            pkgs.append((name, ver, "apt"))
        return pkgs

    def _get_snap_packages(self):
        try:
            result = subprocess.run(
                ["snap", "list"],
                capture_output=True, text=True, timeout=30
            )
            lines = result.stdout.strip().split("\n")
            pkgs = []
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.split()
                name = parts[0]
                ver = parts[1] if len(parts) > 1 else ""
                pkgs.append((name, f"ver: {ver} | snap", "snap"))
            return pkgs
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []

    def _get_flatpak_packages(self):
        try:
            result = subprocess.run(
                ["flatpak", "list", "--app"],
                capture_output=True, text=True, timeout=30
            )
            lines = result.stdout.strip().split("\n")
            pkgs = []
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split("\t")
                name = parts[0]
                desc = parts[2] if len(parts) > 2 else ""
                pkgs.append((name, desc, "flatpak"))
            return pkgs
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []

    def _populate_tabs(self, apt_pkgs, snap_pkgs, flatpak_pkgs):
        while self.notebook.get_n_pages() > 0:
            self.notebook.remove_page(0)

        if hasattr(self, '_error_log') and self._error_log:
            self.terminal_revealer.set_reveal_child(True)
            for err in self._error_log:
                self._append_terminal(err + "\n")

        self._apt_listbox = self.create_tab(f"Apt ({len(apt_pkgs)})")
        self._snap_listbox = self.create_tab(f"Snap ({len(snap_pkgs)})")
        self._flatpak_listbox = self.create_tab(f"Flatpak ({len(flatpak_pkgs)})")

        self._add_packages_to_listbox(self._apt_listbox, apt_pkgs)
        self._add_packages_to_listbox(self._snap_listbox, snap_pkgs)
        self._add_packages_to_listbox(self._flatpak_listbox, flatpak_pkgs)

        self.all_listboxes = [self._apt_listbox, self._snap_listbox, self._flatpak_listbox]
        self.packages = apt_pkgs + snap_pkgs + flatpak_pkgs

        for listbox in self.all_listboxes:
            for row in listbox.get_children():
                if isinstance(row, PackageRow):
                    row.check.connect("toggled", self._on_check_toggled)

        self.notebook.show_all()
        self.status_label.set_text(f"Ukupno: {len(self.packages)} paketa")
        self.progress.set_fraction(1.0)
        self.progress.set_text(f"Ukupno: {len(self.packages)} paketa")

    def _add_packages_to_listbox(self, listbox, pkgs):
        for name, desc, ptype in pkgs:
            row = PackageRow(name, desc, ptype)
            listbox.add(row)
            row.show_all()

    def _on_check_toggled(self, check):
        self._update_ui()

    def _update_ui(self):
        count = 0
        for listbox in self.all_listboxes:
            for row in listbox.get_children():
                if isinstance(row, PackageRow) and row.check.get_active():
                    count += 1
        self.uninstall_btn.set_sensitive(count > 0)
        self.uninstall_btn.set_label(f"Deinstaliraj selektovane ({count})")

    def on_select_all(self, btn):
        page = self.notebook.get_current_page()
        listbox = self.notebook.get_nth_page(page).get_child()
        for row in listbox.get_children():
            if isinstance(row, PackageRow) and not row.check.get_active():
                row.check.set_active(True)

    def on_deselect_all(self, btn):
        for listbox in self.all_listboxes:
            for row in listbox.get_children():
                if isinstance(row, PackageRow) and row.check.get_active():
                    row.check.set_active(False)

    def on_refresh(self, btn):
        self.load_packages()

    def on_uninstall(self, btn):
        selected = []
        for listbox in self.all_listboxes:
            for row in listbox.get_children():
                if isinstance(row, PackageRow) and row.check.get_active():
                    selected.append(row)
        if not selected:
            return

        self.terminal_revealer.set_reveal_child(True)
        self.terminal_buffer.set_text("")

        self._append_terminal(f"Priprema za deinstalaciju {len(selected)} paketa...\n")
        self.uninstall_btn.set_sensitive(False)
        self.refresh_btn.set_sensitive(False)

        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            message_format="Potrebna je sudo šifra za deinstalaciju"
        )
        dialog.format_secondary_text("Unesi sudo lozinku (neće biti sačuvana):")
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_invisible_char("*")
        entry.connect("activate", lambda e: dialog.response(Gtk.ResponseType.OK))
        box = dialog.get_content_area()
        box.pack_start(entry, False, False, 0)
        dialog.show_all()
        resp = dialog.run()
        password = entry.get_text()
        dialog.destroy()

        if resp != Gtk.ResponseType.OK or not password:
            self._append_terminal("Otkazano.\n")
            self.refresh_btn.set_sensitive(True)
            self._update_ui()
            return

        self._append_terminal("Provjera šifre...\n")
        self.progress.set_fraction(0.0)
        self.progress.set_text("Autentikacija...")

        proc = subprocess.run(
            ["sudo", "-S", "-v"],
            input=password + "\n",
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode != 0:
            self._append_terminal("❌ Pogrešna šifra!\n")
            self.refresh_btn.set_sensitive(True)
            self._update_ui()
            return

        self._password_cached = True
        self._append_terminal("✅ Autentikacija uspješna. Pokrećem deinstalaciju...\n\n")
        thread = threading.Thread(
            target=self._run_removal,
            args=(selected,),
            daemon=True
        )
        thread.start()

    def _run_removal(self, selected):
        total = len(selected)
        for i, row in enumerate(selected):
            text = f"[{i+1}/{total}] Deinstaliram {row.pkg_name} ({row.pkg_type})...\n"
            GLib.idle_add(self._append_terminal, text)
            GLib.idle_add(self.progress.set_fraction, i / total)
            GLib.idle_add(self.progress.set_text, f"{i+1}/{total}")

            try:
                if row.pkg_type == "apt":
                    proc = subprocess.run(
                        ["sudo", "apt", "remove", "-y", row.pkg_name],
                        capture_output=True, text=True, timeout=300
                    )
                elif row.pkg_type == "snap":
                    proc = subprocess.run(
                        ["sudo", "snap", "remove", row.pkg_name],
                        capture_output=True, text=True, timeout=300
                    )
                elif row.pkg_type == "flatpak":
                    proc = subprocess.run(
                        ["flatpak", "remove", "-y", row.pkg_name],
                        capture_output=True, text=True, timeout=300
                    )
                else:
                    continue

                out = (proc.stdout or "") + (proc.stderr or "")
                GLib.idle_add(self._append_terminal, out[:2000])
                if proc.returncode == 0:
                    GLib.idle_add(self._append_terminal, f"✅ {row.pkg_name} deinstaliran\n\n")
                    GLib.idle_add(row.check.set_active, False)
                    GLib.idle_add(self._remove_row_from_listbox, row)
                else:
                    msg = f"❌ Greška ({proc.returncode})\n\n"
                    GLib.idle_add(self._append_terminal, msg)
            except subprocess.TimeoutExpired:
                GLib.idle_add(self._append_terminal, f"⏰ Vremensko ograničenje za {row.pkg_name}\n\n")
            except Exception as e:
                GLib.idle_add(self._append_terminal, f"❌ Izuzetak: {e}\n\n")

        GLib.idle_add(self.progress.set_fraction, 1.0)
        GLib.idle_add(self.progress.set_text, "Završeno")
        GLib.idle_add(self.refresh_btn.set_sensitive, True)
        GLib.idle_add(self._update_ui)
        GLib.idle_add(self._append_terminal, "✅ Deinstalacija završena.\n")

    def _remove_row_from_listbox(self, row):
        parent = row.get_parent()
        if parent:
            parent.remove(row)

    def _append_terminal(self, text):
        end_iter = self.terminal_buffer.get_end_iter()
        self.terminal_buffer.insert(end_iter, text)

    def _show_error(self, msg):
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            message_format=msg
        )
        dialog.run()
        dialog.destroy()

if __name__ == "__main__":
    app = PackageRemover()
    app.show_all()
    Gtk.main()
