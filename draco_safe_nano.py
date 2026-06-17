#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Draco-Safe Nano - Der einfache, sichere Passwort-Manager
Version 1.1.9 | Freeware | MIT-Lizenz
"""
import os, sys, json, secrets, string, hashlib, base64, re, time, shutil, webbrowser
from tkinter import messagebox, filedialog
import customtkinter as ctk
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# ===== KONFIGURATION =====
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")
FARBE_GRUEN = "#1B4D3E"
FARBE_DUNKEL = "#112B1C"
FARBE_WEISS = "#FFFFFF"
FARBE_GRUEN_HELL = "#145A32"
HOMEPAGE = "https://dracondors-heim.de"

# ===== HAUPTKLASSE =====
class DracoSafeNano(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Draco-Safe Nano v1.1.9")
        self.geometry("1100x800")
        self.resizable(True, True)
        self.configure(fg_color=FARBE_DUNKEL)

        self.data_dir = os.path.join(os.path.expanduser("~"), ".draco_safe_nano")
        os.makedirs(self.data_dir, exist_ok=True)
        self.vault_file = os.path.join(self.data_dir, "vault.dat")
        
        self.data = {
            "salt": None,
            "entries": [],
            "categories": ["Allgemein", "Internet", "Banken", "Gaming"],
            "notes": ""
        }
        self.master_password = None
        self.current_category = "Allgemein"
        self.filtered_entries = []
        
        self.keyboard_visible = False
        self.current_focus = None
        self.shift = False
        self.key_buttons = []
        self.keyboard_frame = None
        self.shift_btn = None
        
        self.lock_file = os.path.join(self.data_dir, "lock.dat")
        self.login_attempts = 0
        self.locked_until = 0
        self._load_lock_state()
        
        self.last_activity = time.time()
        self.bind_all("<Any-KeyPress>", self._reset_timer)
        self.bind_all("<Any-Button>", self._reset_timer)
        self.bind_all("<Motion>", self._reset_timer)
        self._check_auto_lock()
        
        self.bind_all("<Control-s>", lambda e: self.save_entry())
        self.bind_all("<Control-n>", lambda e: self.focus_new_entry())
        self.bind_all("<Control-f>", lambda e: self.search_entry.focus_set() if hasattr(self, 'search_entry') else None)
        self.bind_all("<Control-k>", lambda e: self.toggle_keyboard())
        
        self.init_login()
    
    def _reset_timer(self, event=None):
        self.last_activity = time.time()
        
    def _check_auto_lock(self):
        if self.master_password is not None:
            if time.time() - self.last_activity > 300:
                self.lock()
                return
        self.after(1000, self._check_auto_lock)
        
    def _load_lock_state(self):
        if os.path.exists(self.lock_file):
            try:
                with open(self.lock_file, "r") as f:
                    state = json.load(f)
                    self.login_attempts = state.get("attempts", 0)
                    self.locked_until = state.get("locked_until", 0)
            except:
                pass

    def _save_lock_state(self):
        try:
            with open(self.lock_file, "w") as f:
                json.dump({"attempts": self.login_attempts, "locked_until": self.locked_until}, f)
        except:
            pass

    # ===== VERSCHLÜSSELUNG =====
    def _derive_key(self, password, salt, iterations=600000):
        kdf = PBKDF2HMAC(hashes.SHA256(), 32, salt, iterations)
        return kdf.derive(password.encode())
    
    def _encrypt(self, data, password, salt):
        key = self._derive_key(password, salt, 600000)
        nonce = os.urandom(12)
        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce))
        encryptor = cipher.encryptor()
        plaintext = json.dumps(data).encode()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        return salt + nonce + encryptor.tag + ciphertext
    
    def _decrypt(self, encrypted, password):
        if len(encrypted) < 44:
            return None
        salt = encrypted[:16]
        nonce = encrypted[16:28]
        tag = encrypted[28:44]
        ciphertext = encrypted[44:]
        for iters in [600000, 200000]:
            try:
                key = self._derive_key(password, salt, iters)
                cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag))
                decryptor = cipher.decryptor()
                plaintext = decryptor.update(ciphertext) + decryptor.finalize()
                return json.loads(plaintext.decode())
            except:
                continue
        return None
    
    def _load_vault(self, password):
        if not os.path.exists(self.vault_file):
            return None
        try:
            with open(self.vault_file, "rb") as f:
                return self._decrypt(f.read(), password)
        except:
            return None
    
    def _save_vault(self, password):
        salt = self.data.get("salt")
        if salt is None:
            salt = os.urandom(16)
            self.data["salt"] = base64.b64encode(salt).decode()
        else:
            salt = base64.b64decode(salt)
        encrypted = self._encrypt(self.data, password, salt)
        tmp = self.vault_file + ".tmp"
        with open(tmp, "wb") as f:
            f.write(encrypted)
        os.replace(tmp, self.vault_file)
    
    # ===== VIRTUELLE TASTATUR =====
    def toggle_keyboard(self):
        if self.keyboard_visible:
            if self.keyboard_frame:
                self.keyboard_frame.pack_forget()
        else:
            if self.keyboard_frame:
                self.keyboard_frame.pack(side="bottom", fill="x", padx=10, pady=5)
        self.keyboard_visible = not self.keyboard_visible
    
    def set_focus(self, widget):
        self.current_focus = widget
    
    def toggle_shift(self):
        self.shift = not self.shift
        for btn in self.key_buttons:
            text = btn.cget("text")
            if text.isalpha() and (len(text) == 1 or text in ('SS', 'ß')):
                if self.shift:
                    btn.configure(text=text.upper())
                else:
                    btn.configure(text='ß' if text == 'SS' else text.lower())
        if self.shift_btn:
            self.shift_btn.configure(fg_color="#2ecc71" if self.shift else FARBE_GRUEN_HELL)
    
    def key_press(self, char):
        if self.current_focus:
            if self.shift and char.isalpha():
                char = char.upper()
            if isinstance(self.current_focus, ctk.CTkEntry):
                self.current_focus.insert("insert", char)
            elif isinstance(self.current_focus, ctk.CTkTextbox):
                self.current_focus.insert("insert", char)
    
    def key_backspace(self):
        if self.current_focus:
            if isinstance(self.current_focus, ctk.CTkEntry):
                idx = self.current_focus.index("insert")
                if idx > 0:
                    self.current_focus.delete(idx - 1, idx)
            elif isinstance(self.current_focus, ctk.CTkTextbox):
                self.current_focus.delete("insert-1c", "insert")
    
    def key_clear(self):
        if self.current_focus:
            if isinstance(self.current_focus, ctk.CTkEntry):
                self.current_focus.delete(0, "end")
            elif isinstance(self.current_focus, ctk.CTkTextbox):
                self.current_focus.delete("1.0", "end")
    
    def create_keyboard(self, parent):
        self.keyboard_frame = ctk.CTkFrame(parent, fg_color=FARBE_GRUEN)
        self.key_buttons = []
        
        number_frame = ctk.CTkFrame(self.keyboard_frame, fg_color="transparent")
        number_frame.pack(pady=1)
        for char in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']:
            btn = ctk.CTkButton(number_frame, text=char, width=45, height=35, font=("Arial", 12, "bold"), fg_color="#1a5a3a", command=lambda c=char: self.key_press(c))
            btn.pack(side="left", padx=1)
            self.key_buttons.append(btn)
        
        rows = [
            ['q', 'w', 'e', 'r', 't', 'z', 'u', 'i', 'o', 'p', 'ü'],
            ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'ö', 'ä'],
            ['y', 'x', 'c', 'v', 'b', 'n', 'm', 'ß']
        ]
        for row in rows:
            frame = ctk.CTkFrame(self.keyboard_frame, fg_color="transparent")
            frame.pack(pady=1)
            for char in row:
                btn = ctk.CTkButton(frame, text=char, width=45, height=35, font=("Arial", 12, "bold"), fg_color=FARBE_GRUEN_HELL, command=lambda c=char: self.key_press(c))
                btn.pack(side="left", padx=1)
                self.key_buttons.append(btn)
        
        special_rows = [
            ['!', '?', '@', '-', '_', '.', ',', ';', ':', '"', "'"],
            ['#', '+', '*', '=', '/', '(', ')', '[', ']', '{', '}'],
            ['<', '>', '|', '&', '$', '%', '°', '~', '^', '€']
        ]
        for row in special_rows:
            frame = ctk.CTkFrame(self.keyboard_frame, fg_color="transparent")
            frame.pack(pady=1)
            for char in row:
                btn = ctk.CTkButton(frame, text=char, width=40, height=35, font=("Arial", 12, "bold"), fg_color="#254D38", command=lambda c=char: self.key_press(c))
                btn.pack(side="left", padx=1)
                self.key_buttons.append(btn)
        
        control_frame = ctk.CTkFrame(self.keyboard_frame, fg_color="transparent")
        control_frame.pack(pady=1)
        
        self.shift_btn = ctk.CTkButton(control_frame, text="⇧ Shift", width=70, height=35, fg_color=FARBE_GRUEN_HELL, command=self.toggle_shift)
        self.shift_btn.pack(side="left", padx=2)
        
        ctk.CTkButton(control_frame, text="⌫", width=60, height=35, fg_color="#A32424", command=self.key_backspace).pack(side="left", padx=2)
        ctk.CTkButton(control_frame, text="✕ Löschen", width=80, height=35, fg_color="#A32424", command=self.key_clear).pack(side="left", padx=2)
        ctk.CTkButton(control_frame, text="Leerzeichen", width=100, height=35, fg_color="#4A4A4A", command=lambda: self.key_press(" ")).pack(side="left", padx=2)
        ctk.CTkButton(control_frame, text="⌨ Hide", width=80, height=35, fg_color="#4A4A4A", command=self.toggle_keyboard).pack(side="left", padx=2)
    
    # ===== LOGIN =====
    def init_login(self):
        self.login_frame = ctk.CTkFrame(self, fg_color=FARBE_GRUEN, border_color=FARBE_WEISS, border_width=2)
        self.login_frame.pack(fill="both", expand=True, padx=40, pady=40)
        
        ctk.CTkLabel(self.login_frame, text="🐉 Draco-Safe Nano", font=("Arial", 32, "bold"), text_color=FARBE_WEISS).pack(pady=(20, 5))
        ctk.CTkLabel(self.login_frame, text="Einfach. Sicher. Kostenlos.", font=("Arial", 13), text_color=FARBE_WEISS).pack(pady=(0, 20))
        
        frame = ctk.CTkFrame(self.login_frame, fg_color="transparent")
        frame.pack(expand=True)
        
        ctk.CTkLabel(frame, text="Master-Passwort", font=("Arial", 12), text_color=FARBE_WEISS).pack(pady=(10, 0))
        
        pw_frame = ctk.CTkFrame(frame, fg_color="transparent")
        pw_frame.pack(pady=5)
        
        self.pw1 = ctk.CTkEntry(pw_frame, width=200, show="*", font=("Arial", 14))
        self.pw1.pack(side="left", padx=5)
        self.pw1.bind("<FocusIn>", lambda e: self.set_focus(self.pw1))
        
        self.show_pw_btn = ctk.CTkButton(pw_frame, text="👁", width=30, height=30, fg_color="#4A4A4A", command=self.toggle_password_visibility)
        self.show_pw_btn.pack(side="left", padx=2)
        
        ctk.CTkLabel(frame, text="Wiederholen", font=("Arial", 12), text_color=FARBE_WEISS).pack(pady=(10, 0))
        self.pw2 = ctk.CTkEntry(frame, width=250, show="*", font=("Arial", 14))
        self.pw2.pack(pady=5)
        self.pw2.bind("<FocusIn>", lambda e: self.set_focus(self.pw2))
        
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="Login / Neu", width=120, command=self.login).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="⌨ Tastatur", width=100, fg_color="#4A4A4A", command=self.toggle_keyboard).pack(side="left", padx=5)
        
        link_frame = ctk.CTkFrame(self.login_frame, fg_color="transparent")
        link_frame.pack(pady=10)
        homepage_link = ctk.CTkLabel(link_frame, text="🌐 https://dracondors-heim.de", font=("Arial", 10, "underline"), text_color=FARBE_WEISS, cursor="hand2")
        homepage_link.pack()
        homepage_link.bind("<Button-1>", lambda e: webbrowser.open(HOMEPAGE))
        
        self.create_keyboard(self.login_frame)
        self.keyboard_frame.pack_forget()
    
    def toggle_password_visibility(self):
        if self.pw1.cget("show") == "*":
            self.pw1.configure(show="")
            self.show_pw_btn.configure(text="🙈")
        else:
            self.pw1.configure(show="*")
            self.show_pw_btn.configure(text="👁")
            
    def _secure_copy(self, text):
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            if hasattr(self, '_clear_clipboard_id') and self._clear_clipboard_id:
                self.after_cancel(self._clear_clipboard_id)
            def clear():
                try:
                    if self.clipboard_get() == text:
                        self.clipboard_clear()
                        self.update()
                except:
                    pass
            self._clear_clipboard_id = self.after(15000, clear)
    
    def login(self):
        now = time.time()
        if now < self.locked_until:
            messagebox.showerror("Gesperrt", f"Bitte warten Sie {int(self.locked_until - now)} Sekunden.")
            return
        
        p1, p2 = self.pw1.get(), self.pw2.get()
        if not p1 or not p2:
            messagebox.showwarning("", "Passwort eingeben!")
            return
        if p1 != p2:
            messagebox.showerror("", "Passwörter stimmen nicht überein!")
            return
        
        data = self._load_vault(p1)
        if data is None:
            if os.path.exists(self.vault_file):
                self.login_attempts += 1
                if self.login_attempts >= 3:
                    self.locked_until = now + 300
                    self._save_lock_state()
                    messagebox.showerror("Gesperrt", "3 Fehlversuche. Login für 5 Minuten gesperrt.")
                    self.login_attempts = 0
                    self._save_lock_state()
                    return
                self._save_lock_state()
                messagebox.showerror("Fehler", "Falsches Passwort!")
                return
            else:
                if not messagebox.askyesno("", "Neuen Tresor erstellen?"):
                    return
                self.data["salt"] = base64.b64encode(os.urandom(16)).decode()
                self._save_vault(p1)
                messagebox.showinfo("Erfolg", "Tresor wurde erstellt!")
                data = self._load_vault(p1)
        else:
            self.data = data
            self.master_password = p1
            self.login_attempts = 0
            self._save_lock_state()
        
        self.login_frame.pack_forget()
        self.main_app()
    
    # ===== HAUPTFENSTER =====
    def main_app(self):
        main = ctk.CTkFrame(self, fg_color=FARBE_DUNKEL)
        main.pack(fill="both", expand=True, padx=10, pady=10)
        
        left = ctk.CTkFrame(main, width=230, fg_color=FARBE_GRUEN, border_color=FARBE_WEISS, border_width=1)
        left.pack(side="left", fill="y", padx=(0, 10))
        
        ctk.CTkLabel(left, text="📂 Kategorien", font=("Arial", 16, "bold"), text_color=FARBE_WEISS).pack(pady=10)
        self.cat_frame = ctk.CTkScrollableFrame(left, width=210, height=200, fg_color=FARBE_GRUEN)
        self.cat_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.cat_buttons = []
        
        ctk.CTkLabel(left, text="Neue Kategorie:", font=("Arial", 10), text_color=FARBE_WEISS).pack(pady=(10, 0))
        self.new_cat = ctk.CTkEntry(left, width=210, placeholder_text="Name")
        self.new_cat.pack(pady=2)
        self.new_cat.bind("<FocusIn>", lambda e: self.set_focus(self.new_cat))
        ctk.CTkButton(left, text="+ Hinzufügen", width=210, command=self.add_category).pack(pady=2)
        
        ctk.CTkLabel(left, text="", height=10).pack()
        ctk.CTkButton(left, text="💾 Notizen", width=210, fg_color="#4A4A4A", command=self.open_notes).pack(pady=2)
        ctk.CTkButton(left, text="📤 Export (verschlüsselt)", width=210, fg_color="#4A4A4A", command=self.export_data).pack(pady=2)
        ctk.CTkButton(left, text="📥 Import", width=210, fg_color="#4A4A4A", command=self.import_data).pack(pady=2)
        ctk.CTkButton(left, text="⌨ Tastatur (Strg+K)", width=210, fg_color="#4A4A4A", command=self.toggle_keyboard).pack(pady=2)
        
        right = ctk.CTkFrame(main, fg_color=FARBE_GRUEN, border_color=FARBE_WEISS, border_width=1)
        right.pack(side="right", fill="both", expand=True)
        
        top = ctk.CTkFrame(right, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=5)
        self.cat_title = ctk.CTkLabel(top, text=self.current_category, font=("Arial", 18, "bold"), text_color=FARBE_WEISS)
        self.cat_title.pack(side="left", padx=10)
        ctk.CTkLabel(top, text="🔍", font=("Arial", 14), text_color=FARBE_WEISS).pack(side="left", padx=(20, 2))
        self.search_entry = ctk.CTkEntry(top, width=200, placeholder_text="Suchen...")
        self.search_entry.pack(side="left", padx=2)
        self.search_entry.bind("<FocusIn>", lambda e: self.set_focus(self.search_entry))
        self.search_entry.bind("<KeyRelease>", lambda e: self.filter_entries())
        
        header = ctk.CTkFrame(right, fg_color=FARBE_DUNKEL)
        header.pack(fill="x", padx=15, pady=5)
        for t, w in [("Dienst", 200), ("Benutzer", 150), ("Passwort", 150)]:
            ctk.CTkLabel(header, text=t, width=w, font=("Arial", 10, "bold"), text_color=FARBE_WEISS).pack(side="left", padx=3)
        
        list_frame = ctk.CTkFrame(right, fg_color=FARBE_DUNKEL)
        list_frame.pack(fill="both", expand=True, padx=15, pady=5)
        self.entry_list = ctk.CTkTextbox(list_frame, height=180, font=("Consolas", 10), fg_color=FARBE_DUNKEL, state="normal")
        self.entry_list.pack(fill="both", expand=True, padx=10, pady=5)
        self.entry_list.bind("<ButtonRelease-1>", self.on_select)
        
        form = ctk.CTkFrame(right, fg_color=FARBE_GRUEN, border_color=FARBE_WEISS, border_width=1)
        form.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(form, text="Neuer Eintrag:", font=("Arial", 13, "bold"), text_color=FARBE_WEISS).pack(pady=5)
        
        grid = ctk.CTkFrame(form, fg_color="transparent")
        grid.pack(pady=5, padx=10)
        
        ctk.CTkLabel(grid, text="Dienst:", width=70).grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self.e_service = ctk.CTkEntry(grid, width=300)
        self.e_service.grid(row=0, column=1, columnspan=4, padx=5, pady=2, sticky="w")
        self.e_service.bind("<FocusIn>", lambda e: self.set_focus(self.e_service))
        
        ctk.CTkLabel(grid, text="Benutzer:", width=70).grid(row=1, column=0, padx=5, pady=2, sticky="e")
        self.e_user = ctk.CTkEntry(grid, width=200)
        self.e_user.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.e_user.bind("<FocusIn>", lambda e: self.set_focus(self.e_user))
        ctk.CTkButton(grid, text="📋", width=30, fg_color="#4A4A4A", command=lambda: self._secure_copy(self.e_user.get())).grid(row=1, column=2, padx=5, pady=2, sticky="w")
        
        ctk.CTkLabel(grid, text="Passwort:", width=70).grid(row=2, column=0, padx=5, pady=2, sticky="e")
        self.e_pass = ctk.CTkEntry(grid, width=200)
        self.e_pass.grid(row=2, column=1, padx=5, pady=2, sticky="w")
        self.e_pass.bind("<FocusIn>", lambda e: self.set_focus(self.e_pass))
        ctk.CTkButton(grid, text="📋", width=30, fg_color="#4A4A4A", command=lambda: self._secure_copy(self.e_pass.get())).grid(row=2, column=2, padx=5, pady=2, sticky="w")
        self.pw_strength = ctk.CTkLabel(grid, text="", width=80)
        self.pw_strength.grid(row=2, column=3, padx=5, pady=2)
        self.e_pass.bind("<KeyRelease>", self.check_strength)
        ctk.CTkButton(grid, text="🎲 Generator", width=100, fg_color=FARBE_GRUEN_HELL, command=self.gen_password).grid(row=2, column=4, padx=5, pady=2)
        
        ctk.CTkLabel(grid, text="URL:", width=70).grid(row=3, column=0, padx=5, pady=2, sticky="e")
        self.e_url = ctk.CTkEntry(grid, width=400)
        self.e_url.grid(row=3, column=1, columnspan=4, padx=5, pady=2, sticky="w")
        self.e_url.bind("<FocusIn>", lambda e: self.set_focus(self.e_url))
        
        ctk.CTkLabel(grid, text="Notiz:", width=70).grid(row=4, column=0, padx=5, pady=2, sticky="ne")
        self.e_note = ctk.CTkTextbox(grid, height=50, width=400, fg_color=FARBE_DUNKEL)
        self.e_note.grid(row=4, column=1, columnspan=4, padx=5, pady=2, sticky="w")
        self.e_note.bind("<FocusIn>", lambda e: self.set_focus(self.e_note))
        
        btn_row = ctk.CTkFrame(form, fg_color="transparent")
        btn_row.pack(pady=8)
        ctk.CTkButton(btn_row, text="💾 Speichern", width=120, fg_color=FARBE_GRUEN_HELL, command=self.save_entry).pack(side="left", padx=2)
        ctk.CTkButton(btn_row, text="🗑 Löschen", width=100, fg_color="#A32424", command=self.delete_entry).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="🔒 Sperren", width=100, fg_color="#4A4A4A", command=self.lock).pack(side="right", padx=2)
        
        self.create_keyboard(main)
        self.keyboard_frame.pack_forget()
        
        self.render_categories()
        self.render_entries()
    
    # ===== KATEGORIEN =====
    def render_categories(self):
        for b in self.cat_buttons:
            b.destroy()
        self.cat_buttons.clear()
        for cat in self.data["categories"]:
            is_active = (cat == self.current_category)
            b = ctk.CTkButton(self.cat_frame, text=cat, fg_color="#145A32" if is_active else "#254D38", command=lambda x=cat: self.switch_category(x))
            b.pack(fill="x", pady=2)
            self.cat_buttons.append(b)
    
    def switch_category(self, cat):
        self.current_category = cat
        self.cat_title.configure(text=cat)
        self.render_entries()
        self.render_categories()
    
    def add_category(self):
        name = self.new_cat.get().strip()
        if name and name not in self.data["categories"]:
            self.data["categories"].append(name)
            self._save_vault(self.master_password)
            self.new_cat.delete(0, "end")
            self.render_categories()
            messagebox.showinfo("Erfolg", f"Kategorie '{name}' wurde hinzugefügt!")
        elif name in self.data["categories"]:
            messagebox.showwarning("Warnung", "Diese Kategorie existiert bereits!")
        else:
            messagebox.showwarning("Warnung", "Bitte einen Namen eingeben!")
    
    # ===== EINTRÄGE =====
    def render_entries(self):
        self.entry_list.configure(state="normal")
        self.entry_list.delete("1.0", "end")
        entries = [e for e in self.data["entries"] if e.get("category") == self.current_category]
        if self.search_entry.get():
            term = self.search_entry.get().lower()
            entries = [e for e in entries if term in e.get("service", "").lower() or term in e.get("user", "").lower()]
        if not entries:
            self.entry_list.insert("1.0", "Keine Einträge")
        else:
            for e in entries:
                self.entry_list.insert("end", f"{e['service']} | {e['user']} | {e['password']}\n")
        self.entry_list.configure(state="disabled")
    
    def filter_entries(self):
        self.render_entries()
    
    def on_select(self, e):
        try:
            idx = self.entry_list.index("@0,%d" % e.y).split('.')[0]
            line = self.entry_list.get(f"{idx}.0", f"{idx}.end").strip()
            if line and not line.startswith("Keine"):
                entries = [entry for entry in self.data["entries"] if entry.get("category") == self.current_category]
                if self.search_entry.get():
                    term = self.search_entry.get().lower()
                    entries = [entry for entry in entries if term in entry.get("service", "").lower() or term in entry.get("user", "").lower()]
                
                line_index = int(idx) - 1
                if 0 <= line_index < len(entries):
                    entry = entries[line_index]
                    self.e_service.delete(0, "end")
                    self.e_service.insert(0, entry.get("service", ""))
                    self.e_user.delete(0, "end")
                    self.e_user.insert(0, entry.get("user", ""))
                    self.e_pass.delete(0, "end")
                    self.e_pass.insert(0, entry.get("password", ""))
                    self.e_url.delete(0, "end")
                    self.e_url.insert(0, entry.get("url", ""))
                    self.e_note.delete("1.0", "end")
                    self.e_note.insert("1.0", entry.get("note", ""))
        except:
            pass
    
    def save_entry(self):
        service = self.e_service.get().strip()
        if not service:
            messagebox.showwarning("", "Dienst ist Pflicht!")
            return
        user = self.e_user.get().strip()
        password = self.e_pass.get().strip()
        url = self.e_url.get().strip()
        note = self.e_note.get("1.0", "end-1c").strip()
        for i, e in enumerate(self.data["entries"]):
            if e.get("category") == self.current_category and e["service"] == service:
                if messagebox.askyesno("", "Eintrag existiert bereits. Überschreiben?"):
                    self.data["entries"][i] = {"category": self.current_category, "service": service, "user": user, "password": password, "url": url, "note": note}
                else:
                    return
                self._save_vault(self.master_password)
                self.render_entries()
                self.clear_form()
                return
        self.data["entries"].append({"category": self.current_category, "service": service, "user": user, "password": password, "url": url, "note": note})
        self._save_vault(self.master_password)
        self.render_entries()
        self.clear_form()
    
    def clear_form(self):
        self.e_service.delete(0, "end")
        self.e_user.delete(0, "end")
        self.e_pass.delete(0, "end")
        self.e_url.delete(0, "end")
        self.e_note.delete("1.0", "end")
        self.pw_strength.configure(text="")
    
    def delete_entry(self):
        service = self.e_service.get().strip()
        if not service:
            return
        if messagebox.askyesno("Löschen", f"'{service}' wirklich löschen?"):
            self.data["entries"] = [e for e in self.data["entries"] if not (e.get("category") == self.current_category and e["service"] == service)]
            self._save_vault(self.master_password)
            self.render_entries()
            self.clear_form()
    
    def focus_new_entry(self):
        self.e_service.focus_set()
    
    # ===== PASSWORTGENERATOR =====
    def gen_password(self):
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(chars) for _ in range(16))
        self.e_pass.delete(0, "end")
        self.e_pass.insert(0, password)
        self.check_strength()
    
    def check_strength(self, event=None):
        pw = self.e_pass.get()
        score = 0
        if len(pw) >= 12: score += 1
        if len(pw) >= 16: score += 1
        if re.search(r'[A-Z]', pw): score += 1
        if re.search(r'[a-z]', pw): score += 1
        if re.search(r'\d', pw): score += 1
        if re.search(r'[^A-Za-z0-9]', pw): score += 1
        if score >= 5: self.pw_strength.configure(text="💪 Stark", text_color="#2ecc71")
        elif score >= 3: self.pw_strength.configure(text="⚠️ Mittel", text_color="#f39c12")
        else: self.pw_strength.configure(text="❌ Schwach", text_color="#e74c3c")
    
    # ===== NOTIZEN =====
    def open_notes(self):
        win = ctk.CTkToplevel(self)
        win.title("Notizen")
        win.geometry("500x400")
        win.configure(fg_color=FARBE_GRUEN)
        ctk.CTkLabel(win, text="📝 Sichere Notizen", font=("Arial", 16, "bold"), text_color=FARBE_WEISS).pack(pady=10)
        text = ctk.CTkTextbox(win, font=("Consolas", 11), fg_color=FARBE_DUNKEL)
        text.pack(fill="both", expand=True, padx=15, pady=10)
        text.insert("1.0", self.data.get("notes", ""))
        text.bind("<FocusIn>", lambda e: self.set_focus(text))
        def save():
            self.data["notes"] = text.get("1.0", "end-1c")
            self._save_vault(self.master_password)
            win.destroy()
        ctk.CTkButton(win, text="💾 Speichern", width=120, fg_color=FARBE_GRUEN_HELL, command=save).pack(pady=10)
    
    # ===== EXPORT (VERSCHLÜSSELT) =====
    def export_data(self):
        """Exportiert die Daten in eine verschlüsselte .draco-Datei"""
        if not self.master_password:
            messagebox.showerror("Fehler", "Kein Master-Passwort vorhanden!")
            return
        
        path = filedialog.asksaveasfilename(
            defaultextension=".draco",
            filetypes=[("DracoSafe Backup", "*.draco")]
        )
        if path:
            try:
                # Verschlüsselte Kopie der Daten erstellen
                export_data = self.data.copy()
                salt = os.urandom(16)
                export_data["salt"] = base64.b64encode(salt).decode()
                encrypted = self._encrypt(export_data, self.master_password, salt)
                with open(path, "wb") as f:
                    f.write(encrypted)
                messagebox.showinfo("Erfolg", 
                    "Backup wurde verschlüsselt gespeichert!\n\n"
                    "Die Datei kann nur mit Ihrem Master-Passwort geöffnet werden.")
            except Exception as e:
                messagebox.showerror("Fehler", f"Export fehlgeschlagen: {e}")
    
    # ===== IMPORT (VERSCHLÜSSELT) =====
    def import_data(self):
        """Importiert eine verschlüsselte .draco-Datei"""
        path = filedialog.askopenfilename(
            filetypes=[("DracoSafe Backup", "*.draco")]
        )
        if path:
            try:
                with open(path, "rb") as f:
                    encrypted = f.read()
                data = self._decrypt(encrypted, self.master_password)
                if data is None:
                    messagebox.showerror("Fehler", 
                        "Falsches Passwort oder beschädigte Datei!")
                    return
                
                # Daten übernehmen
                self.data = data
                self._save_vault(self.master_password)
                self.render_categories()
                self.render_entries()
                messagebox.showinfo("Erfolg", "Import erfolgreich!")
            except Exception as e:
                messagebox.showerror("Fehler", f"Import fehlgeschlagen: {e}")
    
    # ===== SPERREN =====
    def lock(self):
        self.master_password = None
        self.destroy()
        os.execv(sys.executable, [sys.executable] + sys.argv)

# ===== START =====
if __name__ == "__main__":
    app = DracoSafeNano()
    app.mainloop()
