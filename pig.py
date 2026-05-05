"""
Poem Image Generator
====================
A desktop application that generates poetry-style images with:
- A full-canvas background image
- A centered white card with rounded corners
- Title (left) + Author (right) header
- Centered subtitle
- Circular cropped image
- Multi-line poem/text body
- Live preview and PNG export

Usage: python poem_image_generator.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
import threading
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageFilter
import os
import sys
import io

# ─── Constants ────────────────────────────────────────────────────────────────

CANVAS_W = 1080
CANVAS_H = 1350
PREVIEW_SCALE = 0.42          # Scale factor for live preview
CARD_MARGIN_X = 0.10          # Card horizontal margin as fraction of canvas width
CARD_MARGIN_Y = 0.06          # Card vertical margin as fraction of canvas height
CARD_RADIUS = 32              # Rounded corner radius on the white card
CIRCLE_IMG_DIAM = 180         # Diameter of circular image (pixels, full-res)
FONT_FAMILIES = [
    "Georgia", "Times New Roman", "Palatino", "Book Antiqua",
    "Arial", "Helvetica", "Verdana", "Trebuchet MS",
    "Courier New", "DejaVu Serif", "DejaVu Sans",
]

# Background + card colors
CARD_COLOR = (255, 255, 255, 230)   # White with slight transparency
BG_FALLBACK = (200, 185, 170)        # Warm beige if no bg image

# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_pil_font(family: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Try to load a truetype font; fall back to default if unavailable."""
    variants = []
    if bold:
        variants += [
            f"/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            f"/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
            f"/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        ]
    variants += [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in variants:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_circle_image(img: Image.Image, diameter: int) -> Image.Image:
    """Crop and resize image to a circular thumbnail."""
    img = img.convert("RGBA")
    # Crop to square (center)
    w, h = img.size
    min_dim = min(w, h)
    left = (w - min_dim) // 2
    top = (h - min_dim) // 2
    img = img.crop((left, top, left + min_dim, top + min_dim))
    img = img.resize((diameter, diameter), Image.LANCZOS)

    # Create circular mask
    mask = Image.new("L", (diameter, diameter), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, diameter - 1, diameter - 1), fill=255)

    result = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


def rounded_rectangle(draw: ImageDraw.ImageDraw, xy, radius: int, fill, outline=None, outline_width=0):
    """Draw a rounded rectangle on a PIL ImageDraw context."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                           outline=outline, width=outline_width)


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            lines.append("")
            continue
        words = paragraph.split()
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            bbox = font.getbbox(test)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


# ─── Image Renderer ───────────────────────────────────────────────────────────

def render_image(params: dict) -> Image.Image:
    """
    Build the final composite image from params dict.
    Returns a PIL Image at full resolution (CANVAS_W x CANVAS_H).
    """
    W, H = CANVAS_W, CANVAS_H

    # ── 1. Background ──────────────────────────────────────────────────────
    if params.get("bg_image"):
        bg = params["bg_image"].convert("RGB").resize((W, H), Image.LANCZOS)
        # Subtle blur / darken to make card pop
        if params.get("bg_blur", 0) > 0:
            bg = bg.filter(ImageFilter.GaussianBlur(params["bg_blur"]))
    else:
        bg = Image.new("RGB", (W, H), BG_FALLBACK)

    canvas = bg.copy().convert("RGBA")

    # ── 2. White card ─────────────────────────────────────────────────────
    card_x0 = int(W * CARD_MARGIN_X)
    card_x1 = W - card_x0
    card_y0 = int(H * CARD_MARGIN_Y)
    card_y1 = H - card_y0

    card_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card_layer)
    rounded_rectangle(
        card_draw,
        (card_x0, card_y0, card_x1, card_y1),
        CARD_RADIUS,
        fill=(255, 255, 255, 235),
        outline=(220, 215, 210, 180),
        outline_width=2,
    )
    canvas = Image.alpha_composite(canvas, card_layer)

    # ── 3. Drawing context on card ────────────────────────────────────────
    draw = ImageDraw.Draw(canvas)

    padding = params.get("padding", 60)
    inner_x0 = card_x0 + padding
    inner_x1 = card_x1 - padding
    inner_w = inner_x1 - inner_x0
    y_cursor = card_y0 + padding

    # Font sizes from params
    title_size   = params.get("title_size", 34)
    author_size  = params.get("author_size", 34)
    subtitle_size= params.get("subtitle_size", 28)
    body_size    = params.get("body_size", 30)

    text_color  = params.get("text_color", (30, 30, 30))
    body_align  = params.get("body_align", "left")  # "left" | "center" | "right"

    font_title    = load_pil_font("Georgia", title_size, bold=True)
    font_author   = load_pil_font("Georgia", author_size, bold=True)
    font_subtitle = load_pil_font("Georgia", subtitle_size, bold=True)
    font_body     = load_pil_font("Georgia", body_size, bold=False)

    # ── 4. Title (left) + Author (right) ──────────────────────────────────
    title_text  = params.get("title", "")
    author_text = params.get("author", "")

    if title_text or author_text:
        row_h = max(
            (font_title.getbbox(title_text)[3] if title_text else 0),
            (font_author.getbbox(author_text)[3] if author_text else 0),
        )
        if title_text:
            draw.text((inner_x0, y_cursor), title_text, font=font_title, fill=text_color)
        if author_text:
            aw = font_author.getbbox(author_text)[2]
            draw.text((inner_x1 - aw, y_cursor), author_text, font=font_author, fill=text_color)
        y_cursor += row_h + 20

        # Thin divider line
        draw.line([(inner_x0, y_cursor), (inner_x1, y_cursor)], fill=(180, 170, 160, 200), width=1)
        y_cursor += 24

    # ── 5. Subtitle ───────────────────────────────────────────────────────
    subtitle_text = params.get("subtitle", "")
    if subtitle_text:
        sw = font_subtitle.getbbox(subtitle_text)[2]
        sx = inner_x0 + (inner_w - sw) // 2
        draw.text((sx, y_cursor), subtitle_text, font=font_subtitle, fill=text_color)
        y_cursor += font_subtitle.getbbox(subtitle_text)[3] + 24

    # ── 6. Circular image ─────────────────────────────────────────────────
    circle_img = params.get("circle_image")
    if circle_img:
        diam = CIRCLE_IMG_DIAM
        circ = make_circle_image(circle_img, diam)
        # Add subtle shadow behind circle
        shadow = Image.new("RGBA", (diam + 12, diam + 12), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        s_draw.ellipse((4, 4, diam + 8, diam + 8), fill=(0, 0, 0, 60))
        shadow = shadow.filter(ImageFilter.GaussianBlur(6))
        cx = inner_x0 + (inner_w - diam) // 2
        canvas.paste(shadow, (cx - 6, y_cursor - 4), shadow)
        canvas.paste(circ, (cx, y_cursor), circ)
        y_cursor += diam + 36

        draw = ImageDraw.Draw(canvas)  # Refresh draw after paste

    # ── 7. Body text ──────────────────────────────────────────────────────
    body_text = params.get("body", "")
    if body_text:
        lines = wrap_text(body_text, font_body, inner_w)
        line_height = int(body_size * 1.55)

        for line in lines:
            if line == "":
                y_cursor += line_height // 2
                continue

            lw = font_body.getbbox(line)[2] if line else 0

            if body_align == "center":
                lx = inner_x0 + (inner_w - lw) // 2
            elif body_align == "right":
                lx = inner_x1 - lw
            else:
                lx = inner_x0

            draw.text((lx, y_cursor), line, font=font_body, fill=text_color)
            y_cursor += line_height

    return canvas.convert("RGB")


# ─── Main Application ─────────────────────────────────────────────────────────

class PoemImageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Poem Image Generator")
        self.resizable(True, True)
        self.configure(bg="#1e1e2e")
        self.preview_scale = PREVIEW_SCALE

        # State
        self.bg_image: Image.Image | None = None
        self.circle_image: Image.Image | None = None
        self._preview_img_ref = None   # keep reference so GC doesn't collect
        self._render_pending = False

        self._build_ui()
        self._schedule_preview()

    # ── UI Construction ───────────────────────────────────────────────────

    def _build_ui(self):
        # ── Style ──
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TLabel",      background="#1e1e2e", foreground="#cdd6f4", font=("Helvetica", 11))
        style.configure("TFrame",      background="#1e1e2e")
        style.configure("TLabelframe", background="#1e1e2e", foreground="#89b4fa", font=("Helvetica", 11, "bold"))
        style.configure("TLabelframe.Label", background="#1e1e2e", foreground="#89b4fa")
        style.configure("TEntry",      fieldbackground="#313244", foreground="#cdd6f4", insertcolor="#cdd6f4")
        style.configure("TSpinbox",    fieldbackground="#313244", foreground="#cdd6f4", arrowcolor="#cdd6f4")
        style.configure("TCombobox",   fieldbackground="#313244", foreground="#cdd6f4")
        style.configure("TButton",     background="#89b4fa", foreground="#1e1e2e", font=("Helvetica", 11, "bold"), padding=6)
        style.map("TButton", background=[("active", "#b4befe")])

        # ── Root layout: left panel | right preview ──
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Left scrollable panel
        left_outer = ttk.Frame(self, width=440)
        left_outer.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        left_outer.grid_propagate(False)
        left_outer.rowconfigure(0, weight=1)
        left_outer.columnconfigure(0, weight=1)

        canvas_scroll = tk.Canvas(left_outer, bg="#1e1e2e", highlightthickness=0, width=440)
        scrollbar = ttk.Scrollbar(left_outer, orient="vertical", command=canvas_scroll.yview)
        canvas_scroll.configure(yscrollcommand=scrollbar.set)
        canvas_scroll.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.left_frame = ttk.Frame(canvas_scroll)
        self.left_frame_id = canvas_scroll.create_window((0, 0), window=self.left_frame, anchor="nw")

        def _on_frame_configure(event):
            canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all"))
        def _on_canvas_configure(event):
            canvas_scroll.itemconfig(self.left_frame_id, width=event.width)

        self.left_frame.bind("<Configure>", _on_frame_configure)
        canvas_scroll.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas_scroll.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas_scroll.bind_all("<MouseWheel>", _on_mousewheel)
        canvas_scroll.bind_all("<Button-4>", lambda e: canvas_scroll.yview_scroll(-1, "units"))
        canvas_scroll.bind_all("<Button-5>", lambda e: canvas_scroll.yview_scroll(1, "units"))

        self._fill_left_panel(self.left_frame)

        # Right preview area
        right_frame = ttk.Frame(self)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        right_frame.rowconfigure(0, weight=0)
        right_frame.rowconfigure(1, weight=1)
        right_frame.rowconfigure(2, weight=0)
        right_frame.columnconfigure(0, weight=1)
        self.right_frame = right_frame

        ttk.Label(right_frame, text="Live Preview", font=("Helvetica", 13, "bold"),
                  foreground="#89b4fa").grid(row=0, column=0, pady=(0, 8))

        # Preview canvas
        pw = int(CANVAS_W * PREVIEW_SCALE)
        ph = int(CANVAS_H * PREVIEW_SCALE)
        self.preview_canvas = tk.Canvas(right_frame, width=pw, height=ph,
                                        bg="#313244", highlightthickness=2,
                                        highlightbackground="#585b70")
        self.preview_canvas.grid(row=1, column=0, sticky="n")

        # Download button at bottom of preview
        ttk.Button(right_frame, text="⬇  Download PNG",
                   command=self._export_image).grid(row=2, column=0, pady=16)

        # Keep preview canvas visible across different screen sizes.
        right_frame.bind("<Configure>", self._on_right_frame_resize)

    def _fill_left_panel(self, parent):
        pad = {"padx": 12, "pady": 6}

        # ── Images ──────────────────────────────────────────────────────
        img_frame = ttk.LabelFrame(parent, text="  Images  ", padding=10)
        img_frame.pack(fill="x", **pad)
        img_frame.columnconfigure(0, weight=1)
        img_frame.columnconfigure(1, minsize=190)
        img_frame.columnconfigure(2, minsize=64)

        self.bg_label = ttk.Label(img_frame, text="No background image", foreground="#6c7086")
        self.bg_label.grid(row=0, column=0, sticky="w", padx=4)
        ttk.Button(img_frame, text="Choose Background",
                   command=self._pick_bg).grid(row=0, column=1, padx=4, sticky="ew")

        ttk.Button(img_frame, text="Clear",
                   command=self._clear_bg).grid(row=0, column=2, padx=2, sticky="ew")

        self.circ_label = ttk.Label(img_frame, text="No circular image", foreground="#6c7086")
        self.circ_label.grid(row=1, column=0, sticky="w", padx=4, pady=(8, 0))
        ttk.Button(img_frame, text="Choose Circular Image",
                   command=self._pick_circle).grid(row=1, column=1, padx=4, pady=(8, 0), sticky="ew")

        ttk.Button(img_frame, text="Clear",
                   command=self._clear_circle).grid(row=1, column=2, padx=2, pady=(8, 0), sticky="ew")

        # Background blur slider
        ttk.Label(img_frame, text="Background blur:").grid(row=2, column=0, sticky="w", padx=4, pady=(8, 0))
        self.bg_blur_var = tk.IntVar(value=0)
        blur_slider = ttk.Scale(img_frame, from_=0, to=20, variable=self.bg_blur_var,
                                orient="horizontal", length=120,
                                command=lambda _: self._schedule_preview())
        blur_slider.grid(row=2, column=1, sticky="ew", padx=4, pady=(8, 0))

        # ── Text Content ─────────────────────────────────────────────────
        text_frame = ttk.LabelFrame(parent, text="  Text Content  ", padding=10)
        text_frame.pack(fill="x", **pad)
        text_frame.columnconfigure(1, weight=1)

        fields = [
            ("Title", "title_var", "Cien sonetos de amor"),
            ("Author", "author_var", "Pablo Neruda"),
            ("Subtitle", "subtitle_var", "XLIV"),
        ]
        for i, (label, varname, default) in enumerate(fields):
            ttk.Label(text_frame, text=label + ":").grid(row=i, column=0, sticky="w", pady=3, padx=4)
            var = tk.StringVar(value=default)
            setattr(self, varname, var)
            entry = ttk.Entry(text_frame, textvariable=var, width=34)
            entry.grid(row=i, column=1, sticky="ew", pady=3, padx=4)
            var.trace_add("write", lambda *_: self._schedule_preview())

        ttk.Label(text_frame, text="Body Text:").grid(row=3, column=0, sticky="nw", pady=(8, 3), padx=4)
        self.body_text = tk.Text(text_frame, width=34, height=12,
                                 bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
                                 font=("Georgia", 11), relief="flat", padx=6, pady=6,
                                 wrap="word")
        self.body_text.grid(row=3, column=1, sticky="ew", pady=(8, 3), padx=4)
        self.body_text.insert("1.0",
            "Sabrás que no te amo y que te amo\n"
            "puesto que de dos modos es la vida,\n"
            "la palabra es un ala del silencio,\n"
            "el fuego tiene una mitad de frío.\n\n"
            "Yo te amo para comenzar a amarte,\n"
            "para recomenzar el infinito\n"
            "y para no dejar de amarte nunca:\n"
            "por eso no te amo todavía.\n\n"
            "Te amo y no te amo como si tuviera\n"
            "en mis manos las llaves de la dicha\n"
            "y un incierto destino desdichado.\n\n"
            "Mi amor tiene dos vidas para armarte.\n"
            "Por eso te amo cuando no te amo\n"
            "y por eso te amo cuando te amo."
        )
        self.body_text.bind("<KeyRelease>", lambda _: self._schedule_preview())

        # ── Typography ───────────────────────────────────────────────────
        typo_frame = ttk.LabelFrame(parent, text="  Typography  ", padding=10)
        typo_frame.pack(fill="x", **pad)
        typo_frame.columnconfigure(1, weight=1)

        size_fields = [
            ("Title size", "title_size_var", 34),
            ("Author size", "author_size_var", 34),
            ("Subtitle size", "subtitle_size_var", 28),
            ("Body size", "body_size_var", 30),
        ]
        for i, (label, varname, default) in enumerate(size_fields):
            ttk.Label(typo_frame, text=label + ":").grid(row=i, column=0, sticky="w", padx=4, pady=3)
            var = tk.IntVar(value=default)
            setattr(self, varname, var)
            spin = ttk.Spinbox(typo_frame, from_=10, to=80, textvariable=var, width=6,
                               command=self._schedule_preview)
            spin.grid(row=i, column=1, sticky="w", padx=4, pady=3)
            var.trace_add("write", lambda *_: self._schedule_preview())

        # Text alignment
        ttk.Label(typo_frame, text="Body align:").grid(row=len(size_fields), column=0, sticky="w", padx=4, pady=3)
        self.align_var = tk.StringVar(value="left")
        align_combo = ttk.Combobox(typo_frame, textvariable=self.align_var,
                                   values=["left", "center", "right"], state="readonly", width=10)
        align_combo.grid(row=len(size_fields), column=1, sticky="w", padx=4, pady=3)
        self.align_var.trace_add("write", lambda *_: self._schedule_preview())

        # ── Layout ───────────────────────────────────────────────────────
        layout_frame = ttk.LabelFrame(parent, text="  Layout  ", padding=10)
        layout_frame.pack(fill="x", **pad)
        layout_frame.columnconfigure(1, weight=1)

        ttk.Label(layout_frame, text="Card padding:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        self.padding_var = tk.IntVar(value=60)
        pad_spin = ttk.Spinbox(layout_frame, from_=20, to=200, textvariable=self.padding_var,
                               width=6, command=self._schedule_preview)
        pad_spin.grid(row=0, column=1, sticky="w", padx=4, pady=3)
        self.padding_var.trace_add("write", lambda *_: self._schedule_preview())

        # Export resolution multiplier
        ttk.Label(layout_frame, text="Export scale:").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        self.export_scale_var = tk.IntVar(value=2)
        ttk.Combobox(layout_frame, textvariable=self.export_scale_var,
                     values=[1, 2, 3], state="readonly", width=6).grid(
            row=1, column=1, sticky="w", padx=4, pady=3)
        ttk.Label(layout_frame, text="× (1=1080px, 2=2160px)",
                  foreground="#6c7086", font=("Helvetica", 9)).grid(
            row=1, column=2, sticky="w", padx=4)

        # Bottom spacer
        ttk.Label(parent, text="").pack()

    # ── Image Pickers ─────────────────────────────────────────────────────

    def _pick_bg(self):
        path = filedialog.askopenfilename(
            title="Choose background image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All", "*.*")]
        )
        if path:
            try:
                self.bg_image = Image.open(path)
                name = os.path.basename(path)
                self.bg_label.config(text=f"✓ {name[:28]}", foreground="#a6e3a1")
                self._schedule_preview()
            except Exception as e:
                messagebox.showerror("Error", f"Could not load image:\n{e}")

    def _clear_bg(self):
        self.bg_image = None
        self.bg_label.config(text="No background image", foreground="#6c7086")
        self._schedule_preview()

    def _pick_circle(self):
        path = filedialog.askopenfilename(
            title="Choose circular image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All", "*.*")]
        )
        if path:
            try:
                self.circle_image = Image.open(path)
                name = os.path.basename(path)
                self.circ_label.config(text=f"✓ {name[:28]}", foreground="#a6e3a1")
                self._schedule_preview()
            except Exception as e:
                messagebox.showerror("Error", f"Could not load image:\n{e}")

    def _clear_circle(self):
        self.circle_image = None
        self.circ_label.config(text="No circular image", foreground="#6c7086")
        self._schedule_preview()

    # ── Preview Rendering ─────────────────────────────────────────────────

    def _build_params(self) -> dict:
        """Collect all UI values into a params dict for the renderer."""
        return {
            "bg_image":     self.bg_image,
            "circle_image": self.circle_image,
            "bg_blur":      self.bg_blur_var.get(),
            "title":        self.title_var.get(),
            "author":       self.author_var.get(),
            "subtitle":     self.subtitle_var.get(),
            "body":         self.body_text.get("1.0", "end-1c"),
            "title_size":   self.title_size_var.get(),
            "author_size":  self.author_size_var.get(),
            "subtitle_size":self.subtitle_size_var.get(),
            "body_size":    self.body_size_var.get(),
            "body_align":   self.align_var.get(),
            "padding":      self.padding_var.get(),
        }

    def _schedule_preview(self, *_):
        """Debounce: only re-render preview 250 ms after last change."""
        if not self._render_pending:
            self._render_pending = True
            self.after(250, self._render_preview)

    def _render_preview(self):
        self._render_pending = False
        params = self._build_params()

        def _do_render():
            try:
                img = render_image(params)
                # Scale down for preview
                pw = max(220, int(CANVAS_W * self.preview_scale))
                ph = max(280, int(CANVAS_H * self.preview_scale))
                thumb = img.resize((pw, ph), Image.LANCZOS)
                self.after(0, lambda: self._show_preview(thumb))
            except Exception as e:
                print(f"Preview render error: {e}")

        t = threading.Thread(target=_do_render, daemon=True)
        t.start()

    def _show_preview(self, img: Image.Image):
        """Display rendered preview in the canvas widget."""
        photo = ImageTk.PhotoImage(img)
        self._preview_img_ref = photo   # prevent GC
        self.preview_canvas.configure(width=img.width, height=img.height)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(0, 0, anchor="nw", image=photo)

    def _on_right_frame_resize(self, event):
        """Scale preview so title/canvas/button remain visible on typical PC screens."""
        available_w = max(260, event.width - 24)
        available_h = max(320, event.height - 130)

        fit_scale = min(PREVIEW_SCALE, available_w / CANVAS_W, available_h / CANVAS_H)
        fit_scale = max(0.24, fit_scale)

        if abs(fit_scale - self.preview_scale) > 0.01:
            self.preview_scale = fit_scale
            self._schedule_preview()

    # ── Export ────────────────────────────────────────────────────────────

    def _export_image(self):
        path = filedialog.asksaveasfilename(
            title="Save image as...",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")],
            initialfile="poem_image.png",
        )
        if not path:
            return

        scale = self.export_scale_var.get()
        params = self._build_params()

        # Scale canvas dimensions for high-res export
        global CANVAS_W, CANVAS_H, CIRCLE_IMG_DIAM
        orig_W, orig_H, orig_D = CANVAS_W, CANVAS_H, CIRCLE_IMG_DIAM
        CANVAS_W *= scale
        CANVAS_H *= scale
        CIRCLE_IMG_DIAM *= scale

        # Scale all font sizes
        for key in ("title_size", "author_size", "subtitle_size", "body_size"):
            params[key] = params[key] * scale
        params["padding"] = params["padding"] * scale

        try:
            img = render_image(params)
        finally:
            CANVAS_W, CANVAS_H, CIRCLE_IMG_DIAM = orig_W, orig_H, orig_D

        ext = os.path.splitext(path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            img.save(path, "JPEG", quality=95, dpi=(300, 300))
        else:
            img.save(path, "PNG", dpi=(300, 300))

        messagebox.showinfo("Saved!", f"Image saved to:\n{path}\n\nSize: {img.size[0]}×{img.size[1]} px")


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = PoemImageApp()

    # Window sizing (fit to current screen while keeping controls visible).
    screen_w = app.winfo_screenwidth()
    screen_h = app.winfo_screenheight()

    start_w = min(1400, max(1100, int(screen_w * 0.9)))
    start_h = min(900, max(680, int(screen_h * 0.9)))
    pos_x = max(0, (screen_w - start_w) // 2)
    pos_y = max(0, (screen_h - start_h) // 2)

    app.minsize(980, 680)
    app.geometry(f"{start_w}x{start_h}+{pos_x}+{pos_y}")

    # Trigger initial preview render
    app.after(400, app._schedule_preview)

    app.mainloop()
