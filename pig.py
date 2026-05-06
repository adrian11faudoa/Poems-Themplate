"""
Poem Image Generator
Desktop app to generate poem-style images with interactive preview editing.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageFilter
import os

CANVAS_W = 1080
CANVAS_H = 1350
PREVIEW_SCALE = 0.42
CARD_MARGIN_X = 0.10
CARD_MARGIN_Y = 0.06
CARD_RADIUS = 32
CIRCLE_IMG_DIAM = 180
BG_FALLBACK = (200, 185, 170)
DEFAULT_TITLE = "Cien sonetos de amor"
DEFAULT_AUTHOR = "Pablo Neruda"
DEFAULT_SUBTITLE = "XLIV"
DEFAULT_BODY_TEXT = (
    "Sabras que no te amo y que te amo\n"
    "puesto que de dos modos es la vida,\n"
    "la palabra es un ala del silencio,\n"
    "el fuego tiene una mitad de frio.\n\n"
    "Yo te amo para comenzar a amarte,\n"
    "para recomenzar el infinito\n"
    "y para no dejar de amarte nunca:\n"
    "por eso no te amo todavia.\n\n"
    "Te amo y no te amo como si tuviera\n"
    "en mis manos las llaves de la dicha\n"
    "y un incierto destino desdichado.\n\n"
    "Mi amor tiene dos vidas para armarte.\n"
    "Por eso te amo cuando no te amo\n"
    "y por eso te amo cuando te amo."
)


def load_pil_font(family: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    variants = []
    if bold:
        variants += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        ]
    variants += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in variants:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_circle_image(img: Image.Image, diameter: int) -> Image.Image:
    img = img.convert("RGBA")
    w, h = img.size
    min_dim = min(w, h)
    left = (w - min_dim) // 2
    top = (h - min_dim) // 2
    img = img.crop((left, top, left + min_dim, top + min_dim))
    img = img.resize((diameter, diameter), Image.LANCZOS)

    mask = Image.new("L", (diameter, diameter), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, diameter - 1, diameter - 1), fill=255)

    result = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


def rounded_rectangle(draw: ImageDraw.ImageDraw, xy, radius: int, fill, outline=None, outline_width=0):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=outline_width)


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
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


def render_image(
    params: dict,
    canvas_size: tuple[int, int] = (CANVAS_W, CANVAS_H),
    circle_diameter: int = CIRCLE_IMG_DIAM,
    return_layout: bool = False,
) -> Image.Image | tuple[Image.Image, dict]:
    W, H = canvas_size
    min_card_w = 220
    min_card_h = 260

    def _clamp(v, lo, hi):
        return max(lo, min(hi, v))

    def _offset_for(name: str) -> tuple[int, int]:
        offsets = params.get("element_offsets", {}) or {}
        raw = offsets.get(name, (0, 0))
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            return int(raw[0]), int(raw[1])
        return 0, 0

    def _text_box(font_obj, text, x, y):
        if not text:
            return None
        bbox = font_obj.getbbox(text)
        tw = max(0, bbox[2] - bbox[0])
        th = max(0, bbox[3] - bbox[1])
        return (int(x), int(y), int(x + tw), int(y + th))

    if params.get("bg_image"):
        bg = params["bg_image"].convert("RGB").resize((W, H), Image.LANCZOS)
        if params.get("bg_blur", 0) > 0:
            bg = bg.filter(ImageFilter.GaussianBlur(params["bg_blur"]))
    else:
        bg = Image.new("RGB", (W, H), BG_FALLBACK)
    canvas = bg.copy().convert("RGBA")

    default_card = (
        int(W * CARD_MARGIN_X),
        int(H * CARD_MARGIN_Y),
        W - int(W * CARD_MARGIN_X),
        H - int(H * CARD_MARGIN_Y),
    )
    card_rect = params.get("card_rect", default_card)
    card_x0, card_y0, card_x1, card_y1 = [int(v) for v in card_rect]
    card_x0 = _clamp(card_x0, 0, W - min_card_w)
    card_y0 = _clamp(card_y0, 0, H - min_card_h)
    card_x1 = _clamp(card_x1, card_x0 + min_card_w, W)
    card_y1 = _clamp(card_y1, card_y0 + min_card_h, H)

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
    draw = ImageDraw.Draw(canvas)

    default_padding = int(params.get("padding", 60))
    sides = params.get("padding_sides", {}) or {}
    pad_l = int(sides.get("left", default_padding))
    pad_r = int(sides.get("right", default_padding))
    pad_t = int(sides.get("top", default_padding))
    pad_b = int(sides.get("bottom", default_padding))

    card_w = card_x1 - card_x0
    card_h = card_y1 - card_y0
    max_hpad = max(10, (card_w - 80) // 2)
    max_vpad = max(10, (card_h - 80) // 2)
    pad_l = _clamp(pad_l, 0, max_hpad)
    pad_r = _clamp(pad_r, 0, max_hpad)
    pad_t = _clamp(pad_t, 0, max_vpad)
    pad_b = _clamp(pad_b, 0, max_vpad)

    inner_x0 = card_x0 + pad_l
    inner_x1 = card_x1 - pad_r
    inner_y0 = card_y0 + pad_t
    inner_w = max(1, inner_x1 - inner_x0)
    y_cursor = inner_y0

    title_size = int(params.get("title_size", 34))
    author_size = int(params.get("author_size", 34))
    subtitle_size = int(params.get("subtitle_size", 28))
    body_size = int(params.get("body_size", 30))
    text_color = params.get("text_color", (30, 30, 30))
    body_align = params.get("body_align", "left")

    font_title = load_pil_font("Georgia", title_size, bold=True)
    font_author = load_pil_font("Georgia", author_size, bold=True)
    font_subtitle = load_pil_font("Georgia", subtitle_size, bold=True)
    font_body = load_pil_font("Georgia", body_size, bold=False)

    layout = {
        "card_rect": (card_x0, card_y0, card_x1, card_y1),
        "elements": {},
    }

    title_text = params.get("title", "")
    author_text = params.get("author", "")
    if title_text or author_text:
        row_h = max(
            (font_title.getbbox(title_text)[3] if title_text else 0),
            (font_author.getbbox(author_text)[3] if author_text else 0),
        )
        tx_off, ty_off = _offset_for("title")
        ax_off, ay_off = _offset_for("author")
        if title_text:
            tx = inner_x0 + tx_off
            ty = y_cursor + ty_off
            draw.text((tx, ty), title_text, font=font_title, fill=text_color)
            layout["elements"]["title"] = _text_box(font_title, title_text, tx, ty)
        if author_text:
            aw = font_author.getbbox(author_text)[2]
            ax = inner_x1 - aw + ax_off
            ay = y_cursor + ay_off
            draw.text((ax, ay), author_text, font=font_author, fill=text_color)
            layout["elements"]["author"] = _text_box(font_author, author_text, ax, ay)
        y_cursor += row_h + 20
        draw.line([(inner_x0, y_cursor), (inner_x1, y_cursor)], fill=(180, 170, 160, 200), width=1)
        y_cursor += 24

    subtitle_text = params.get("subtitle", "")
    if subtitle_text:
        sx_off, sy_off = _offset_for("subtitle")
        sw = font_subtitle.getbbox(subtitle_text)[2]
        sx = inner_x0 + (inner_w - sw) // 2 + sx_off
        sy = y_cursor + sy_off
        draw.text((sx, sy), subtitle_text, font=font_subtitle, fill=text_color)
        layout["elements"]["subtitle"] = _text_box(font_subtitle, subtitle_text, sx, sy)
        y_cursor += font_subtitle.getbbox(subtitle_text)[3] + 24

    circle_img = params.get("circle_image")
    if circle_img:
        cx_off, cy_off = _offset_for("circle")
        diam = circle_diameter
        circ = make_circle_image(circle_img, diam)
        shadow = Image.new("RGBA", (diam + 12, diam + 12), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        s_draw.ellipse((4, 4, diam + 8, diam + 8), fill=(0, 0, 0, 60))
        shadow = shadow.filter(ImageFilter.GaussianBlur(6))
        cx = inner_x0 + (inner_w - diam) // 2 + cx_off
        cy = y_cursor + cy_off
        canvas.paste(shadow, (cx - 6, cy - 4), shadow)
        canvas.paste(circ, (cx, cy), circ)
        layout["elements"]["circle"] = (cx, cy, cx + diam, cy + diam)
        y_cursor += diam + 36

    body_text = params.get("body", "")
    if body_text:
        bx_off, by_off = _offset_for("body")
        lines = wrap_text(body_text, font_body, inner_w)
        line_height = int(body_size * 1.55)
        body_y = y_cursor + by_off
        min_x = None
        max_x = None
        first_y = None
        last_y = body_y
        for line in lines:
            if line == "":
                body_y += line_height // 2
                last_y = body_y
                continue
            lw = font_body.getbbox(line)[2] if line else 0
            if body_align == "center":
                lx = inner_x0 + (inner_w - lw) // 2
            elif body_align == "right":
                lx = inner_x1 - lw
            else:
                lx = inner_x0
            lx += bx_off
            draw.text((lx, body_y), line, font=font_body, fill=text_color)
            if first_y is None:
                first_y = body_y
            min_x = lx if min_x is None else min(min_x, lx)
            max_x = (lx + lw) if max_x is None else max(max_x, lx + lw)
            body_y += line_height
            last_y = body_y
        if first_y is not None and min_x is not None and max_x is not None:
            layout["elements"]["body"] = (int(min_x), int(first_y), int(max_x), int(last_y))

    layout["elements"]["card"] = (card_x0, card_y0, card_x1, card_y1)
    result = canvas.convert("RGB")
    if return_layout:
        return result, layout
    return result


class PoemImageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Poem Image Generator")
        self.resizable(True, True)
        self.configure(bg="#1e1e2e")

        self.bg_image: Image.Image | None = None
        self.circle_image: Image.Image | None = None
        self.layout_state = {
            "element_offsets": {
                "title": [0, 0],
                "author": [0, 0],
                "subtitle": [0, 0],
                "circle": [0, 0],
                "body": [0, 0],
            }
        }
        self._preview_img_ref = None
        self._preview_full_image: Image.Image | None = None
        self._preview_layout: dict = {}
        self._render_after_id = None
        self._render_seq = 0

        self.preview_base_scale = PREVIEW_SCALE
        self.preview_user_zoom = 1.0
        self.preview_pan_x = 0.0
        self.preview_pan_y = 0.0
        self.preview_zoom_min = 0.5
        self.preview_zoom_max = 3.0
        self._is_initial_view = True

        self.selected_element: str | None = None
        self._drag_mode: str | None = None
        self._active_edge: str | None = None
        self._drag_last = (0, 0)

        self._build_ui()
        self._schedule_preview(delay_ms=10)

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Helvetica", 11))
        style.configure("TFrame", background="#1e1e2e")
        style.configure("TLabelframe", background="#1e1e2e", foreground="#89b4fa", font=("Helvetica", 11, "bold"))
        style.configure("TLabelframe.Label", background="#1e1e2e", foreground="#89b4fa")
        style.configure("TEntry", fieldbackground="#313244", foreground="#cdd6f4", insertcolor="#cdd6f4")
        style.configure("TSpinbox", fieldbackground="#313244", foreground="#cdd6f4", arrowcolor="#cdd6f4")
        style.configure("TCombobox", fieldbackground="#313244", foreground="#cdd6f4")
        style.configure("TButton", background="#89b4fa", foreground="#1e1e2e", font=("Helvetica", 11, "bold"), padding=6)
        style.map("TButton", background=[("active", "#b4befe")])

        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

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

        def _on_frame_configure(_event):
            canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all"))

        def _on_canvas_configure(event):
            canvas_scroll.itemconfig(self.left_frame_id, width=event.width)

        self.left_frame.bind("<Configure>", _on_frame_configure)
        canvas_scroll.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            canvas_scroll.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas_scroll.bind_all("<MouseWheel>", _on_mousewheel)
        canvas_scroll.bind_all("<Button-4>", lambda _e: canvas_scroll.yview_scroll(-1, "units"))
        canvas_scroll.bind_all("<Button-5>", lambda _e: canvas_scroll.yview_scroll(1, "units"))

        self._fill_left_panel(self.left_frame)

        right_frame = ttk.Frame(self)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        right_frame.rowconfigure(0, weight=0)
        right_frame.rowconfigure(1, weight=1)
        right_frame.rowconfigure(2, weight=0)
        right_frame.columnconfigure(0, weight=1)

        ttk.Label(right_frame, text="Live Preview", font=("Helvetica", 13, "bold"), foreground="#89b4fa").grid(
            row=0, column=0, pady=(0, 8)
        )

        self.preview_canvas = tk.Canvas(
            right_frame,
            width=max(360, int(CANVAS_W * PREVIEW_SCALE)),
            height=max(440, int(CANVAS_H * PREVIEW_SCALE)),
            bg="#313244",
            highlightthickness=2,
            highlightbackground="#585b70",
            cursor="arrow",
        )
        self.preview_canvas.grid(row=1, column=0, sticky="nsew")
        ttk.Button(right_frame, text="Download Image", command=self._export_image).grid(row=2, column=0, pady=16)

        right_frame.bind("<Configure>", self._on_right_frame_resize)
        self.preview_canvas.bind("<MouseWheel>", self._on_preview_mousewheel)
        self.preview_canvas.bind("<Button-4>", lambda e: self._on_preview_mousewheel(e, delta_override=1))
        self.preview_canvas.bind("<Button-5>", lambda e: self._on_preview_mousewheel(e, delta_override=-1))
        self.preview_canvas.bind("<ButtonPress-1>", self._on_preview_press)
        self.preview_canvas.bind("<B1-Motion>", self._on_preview_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self._on_preview_release)
        self.preview_canvas.bind("<Motion>", self._on_preview_motion)

    def _fill_left_panel(self, parent):
        pad = {"padx": 12, "pady": 6}
        img_frame = ttk.LabelFrame(parent, text="  Images  ", padding=10)
        img_frame.pack(fill="x", **pad)
        img_frame.columnconfigure(0, weight=1)
        img_frame.columnconfigure(1, minsize=190)
        img_frame.columnconfigure(2, minsize=64)

        self.bg_label = ttk.Label(img_frame, text="No background image", foreground="#6c7086")
        self.bg_label.grid(row=0, column=0, sticky="w", padx=4)
        ttk.Button(img_frame, text="Choose Background", command=self._pick_bg).grid(row=0, column=1, padx=4, sticky="ew")
        ttk.Button(img_frame, text="Clear", command=self._clear_bg).grid(row=0, column=2, padx=2, sticky="ew")

        self.circ_label = ttk.Label(img_frame, text="No circular image", foreground="#6c7086")
        self.circ_label.grid(row=1, column=0, sticky="w", padx=4, pady=(8, 0))
        ttk.Button(img_frame, text="Choose Circular Image", command=self._pick_circle).grid(
            row=1, column=1, padx=4, pady=(8, 0), sticky="ew"
        )
        ttk.Button(img_frame, text="Clear", command=self._clear_circle).grid(row=1, column=2, padx=2, pady=(8, 0), sticky="ew")

        ttk.Label(img_frame, text="Background blur:").grid(row=2, column=0, sticky="w", padx=4, pady=(8, 0))
        self.bg_blur_var = tk.IntVar(value=0)
        blur_slider = ttk.Scale(
            img_frame, from_=0, to=20, variable=self.bg_blur_var, orient="horizontal", length=120,
            command=lambda _v: self._schedule_preview()
        )
        blur_slider.grid(row=2, column=1, sticky="ew", padx=4, pady=(8, 0))

        text_frame = ttk.LabelFrame(parent, text="  Text Content  ", padding=10)
        text_frame.pack(fill="x", **pad)
        text_frame.columnconfigure(1, weight=1)
        fields = [
            ("Title", "title_var", DEFAULT_TITLE),
            ("Author", "author_var", DEFAULT_AUTHOR),
            ("Subtitle", "subtitle_var", DEFAULT_SUBTITLE),
        ]
        for i, (label, varname, default) in enumerate(fields):
            ttk.Label(text_frame, text=label + ":").grid(row=i, column=0, sticky="w", pady=3, padx=4)
            var = tk.StringVar(value=default)
            setattr(self, varname, var)
            entry = ttk.Entry(text_frame, textvariable=var, width=34)
            entry.grid(row=i, column=1, sticky="ew", pady=3, padx=4)
            var.trace_add("write", lambda *_: self._schedule_preview())

        ttk.Label(text_frame, text="Body Text:").grid(row=3, column=0, sticky="nw", pady=(8, 3), padx=4)
        self.body_text = tk.Text(
            text_frame, width=34, height=12, bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
            font=("Georgia", 11), relief="flat", padx=6, pady=6, wrap="word"
        )
        self.body_text.grid(row=3, column=1, sticky="ew", pady=(8, 3), padx=4)
        self.body_text.insert("1.0", DEFAULT_BODY_TEXT)
        self.body_text.bind("<KeyRelease>", lambda _e: self._schedule_preview())

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
            spin = ttk.Spinbox(typo_frame, from_=10, to=80, textvariable=var, width=6, command=self._schedule_preview)
            spin.grid(row=i, column=1, sticky="w", padx=4, pady=3)
            var.trace_add("write", lambda *_: self._schedule_preview())

        ttk.Label(typo_frame, text="Body align:").grid(row=len(size_fields), column=0, sticky="w", padx=4, pady=3)
        self.align_var = tk.StringVar(value="left")
        ttk.Combobox(typo_frame, textvariable=self.align_var, values=["left", "center", "right"], state="readonly", width=10).grid(
            row=len(size_fields), column=1, sticky="w", padx=4, pady=3
        )
        self.align_var.trace_add("write", lambda *_: self._schedule_preview())

        layout_frame = ttk.LabelFrame(parent, text="  Layout  ", padding=10)
        layout_frame.pack(fill="x", **pad)
        layout_frame.columnconfigure(1, weight=1)

        ttk.Label(layout_frame, text="Inner card padding:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        self.padding_var = tk.IntVar(value=60)
        ttk.Spinbox(layout_frame, from_=20, to=260, textvariable=self.padding_var, width=6, command=self._schedule_preview).grid(
            row=0, column=1, sticky="w", padx=4, pady=3
        )
        self.padding_var.trace_add("write", lambda *_: self._schedule_preview())

        ttk.Label(layout_frame, text="Card edge padding (L/T/R/B):").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        card_pad_frame = ttk.Frame(layout_frame)
        card_pad_frame.grid(row=1, column=1, sticky="w", padx=4, pady=3)
        self.card_left_var = tk.IntVar(value=int(CANVAS_W * CARD_MARGIN_X))
        self.card_top_var = tk.IntVar(value=int(CANVAS_H * CARD_MARGIN_Y))
        self.card_right_var = tk.IntVar(value=int(CANVAS_W * CARD_MARGIN_X))
        self.card_bottom_var = tk.IntVar(value=int(CANVAS_H * CARD_MARGIN_Y))
        for col, var in enumerate((self.card_left_var, self.card_top_var, self.card_right_var, self.card_bottom_var)):
            ttk.Spinbox(card_pad_frame, from_=0, to=600, textvariable=var, width=5, command=self._schedule_preview).grid(
                row=0, column=col, padx=2
            )
            var.trace_add("write", lambda *_: self._schedule_preview())

        ttk.Label(layout_frame, text="Export scale:").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        self.export_scale_var = tk.IntVar(value=2)
        ttk.Combobox(layout_frame, textvariable=self.export_scale_var, values=[1, 2, 3], state="readonly", width=6).grid(
            row=2, column=1, sticky="w", padx=4, pady=3
        )

        ttk.Label(layout_frame, text="Export format:").grid(row=3, column=0, sticky="w", padx=4, pady=3)
        self.export_format_var = tk.StringVar(value="PNG")
        ttk.Combobox(layout_frame, textvariable=self.export_format_var, values=["PNG", "JPG", "WEBP"], state="readonly", width=8).grid(
            row=3, column=1, sticky="w", padx=4, pady=3
        )

        self.web_opt_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(layout_frame, text="Optimize for Web", variable=self.web_opt_var, command=self._on_web_opt_toggle).grid(
            row=4, column=0, sticky="w", padx=4, pady=3
        )
        self.web_size_var = tk.StringVar(value="1080x1350")
        self.web_size_combo = ttk.Combobox(
            layout_frame, textvariable=self.web_size_var, values=["1080x1350", "1200x1200"], state="disabled", width=10
        )
        self.web_size_combo.grid(row=4, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(layout_frame, text="Tip: drag elements, drag card edges, wheel zoom.", foreground="#6c7086", font=("Helvetica", 9)).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=4, pady=(6, 2)
        )
        self.selected_label = ttk.Label(layout_frame, text="Selected: none", foreground="#94e2d5")
        self.selected_label.grid(row=6, column=0, columnspan=2, sticky="w", padx=4, pady=2)
        ttk.Button(layout_frame, text="Reset to default values", command=self._reset_defaults).grid(
            row=7, column=0, columnspan=2, sticky="ew", padx=4, pady=(6, 2)
        )
        ttk.Label(parent, text="").pack()

    def _pick_bg(self):
        path = filedialog.askopenfilename(
            title="Choose background image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All", "*.*")],
        )
        if path:
            try:
                self.bg_image = Image.open(path)
                self.bg_label.config(text=f"OK {os.path.basename(path)[:28]}", foreground="#a6e3a1")
                self._schedule_preview()
            except Exception as exc:
                messagebox.showerror("Error", f"Could not load image:\n{exc}")

    def _clear_bg(self):
        self.bg_image = None
        self.bg_label.config(text="No background image", foreground="#6c7086")
        self._schedule_preview()

    def _pick_circle(self):
        path = filedialog.askopenfilename(
            title="Choose circular image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All", "*.*")],
        )
        if path:
            try:
                self.circle_image = Image.open(path)
                self.circ_label.config(text=f"OK {os.path.basename(path)[:28]}", foreground="#a6e3a1")
                self._schedule_preview()
            except Exception as exc:
                messagebox.showerror("Error", f"Could not load image:\n{exc}")

    def _clear_circle(self):
        self.circle_image = None
        self.circ_label.config(text="No circular image", foreground="#6c7086")
        self._schedule_preview()

    def _on_web_opt_toggle(self):
        self.web_size_combo.configure(state="readonly" if self.web_opt_var.get() else "disabled")

    def _reset_defaults(self):
        # Image inputs
        self.bg_image = None
        self.circle_image = None
        self.bg_label.config(text="No background image", foreground="#6c7086")
        self.circ_label.config(text="No circular image", foreground="#6c7086")
        self.bg_blur_var.set(0)

        # Text inputs
        self.title_var.set(DEFAULT_TITLE)
        self.author_var.set(DEFAULT_AUTHOR)
        self.subtitle_var.set(DEFAULT_SUBTITLE)
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", DEFAULT_BODY_TEXT)

        # Typography and layout controls
        self.title_size_var.set(34)
        self.author_size_var.set(34)
        self.subtitle_size_var.set(28)
        self.body_size_var.set(30)
        self.align_var.set("left")
        self.padding_var.set(60)
        self.card_left_var.set(int(CANVAS_W * CARD_MARGIN_X))
        self.card_top_var.set(int(CANVAS_H * CARD_MARGIN_Y))
        self.card_right_var.set(int(CANVAS_W * CARD_MARGIN_X))
        self.card_bottom_var.set(int(CANVAS_H * CARD_MARGIN_Y))

        # Export controls
        self.export_scale_var.set(2)
        self.export_format_var.set("PNG")
        self.web_opt_var.set(False)
        self.web_size_var.set("1080x1350")
        self._on_web_opt_toggle()

        # Interactive state
        self.layout_state["element_offsets"] = {
            "title": [0, 0],
            "author": [0, 0],
            "subtitle": [0, 0],
            "circle": [0, 0],
            "body": [0, 0],
        }
        self._set_selected(None)
        self._drag_mode = None
        self._active_edge = None
        self.preview_user_zoom = 1.0
        self.preview_pan_x = 0.0
        self.preview_pan_y = 0.0
        self._is_initial_view = True

        self._schedule_preview(delay_ms=10)

    def _build_params(self) -> dict:
        uniform_pad = self.padding_var.get()
        card_rect = (
            self.card_left_var.get(),
            self.card_top_var.get(),
            CANVAS_W - self.card_right_var.get(),
            CANVAS_H - self.card_bottom_var.get(),
        )
        return {
            "bg_image": self.bg_image,
            "circle_image": self.circle_image,
            "bg_blur": self.bg_blur_var.get(),
            "title": self.title_var.get(),
            "author": self.author_var.get(),
            "subtitle": self.subtitle_var.get(),
            "body": self.body_text.get("1.0", "end-1c"),
            "title_size": self.title_size_var.get(),
            "author_size": self.author_size_var.get(),
            "subtitle_size": self.subtitle_size_var.get(),
            "body_size": self.body_size_var.get(),
            "body_align": self.align_var.get(),
            "padding": uniform_pad,
            "padding_sides": {"left": uniform_pad, "right": uniform_pad, "top": uniform_pad, "bottom": uniform_pad},
            "card_rect": card_rect,
            "element_offsets": {k: tuple(v) for k, v in self.layout_state["element_offsets"].items()},
        }

    def _schedule_preview(self, *_args, delay_ms=120):
        if self._render_after_id is not None:
            try:
                self.after_cancel(self._render_after_id)
            except Exception:
                pass
        self._render_after_id = self.after(delay_ms, self._render_preview)

    def _render_preview(self):
        self._render_after_id = None
        params = self._build_params()
        self._render_seq += 1
        seq = self._render_seq

        def _do_render():
            try:
                img, layout = render_image(params, return_layout=True)
                self.after(0, lambda: self._on_preview_rendered(seq, img, layout))
            except Exception as exc:
                print(f"Preview render error: {exc}")

        threading.Thread(target=_do_render, daemon=True).start()

    def _on_preview_rendered(self, seq: int, img: Image.Image, layout: dict):
        if seq != self._render_seq:
            return
        self._preview_full_image = img
        self._preview_layout = layout
        if self._is_initial_view:
            self._center_preview()
            self._is_initial_view = False
        self._refresh_preview_canvas()

    def _effective_scale(self) -> float:
        return max(0.01, self.preview_base_scale * self.preview_user_zoom)

    def _world_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        s = self._effective_scale()
        return x * s + self.preview_pan_x, y * s + self.preview_pan_y

    def _canvas_to_world(self, x: float, y: float) -> tuple[float, float]:
        s = self._effective_scale()
        return (x - self.preview_pan_x) / s, (y - self.preview_pan_y) / s

    def _center_preview(self):
        s = self._effective_scale()
        cw = max(1, self.preview_canvas.winfo_width())
        ch = max(1, self.preview_canvas.winfo_height())
        self.preview_pan_x = (cw - CANVAS_W * s) / 2
        self.preview_pan_y = (ch - CANVAS_H * s) / 2

    def _refresh_preview_canvas(self):
        if self._preview_full_image is None:
            return
        s = self._effective_scale()
        dw = max(1, int(CANVAS_W * s))
        dh = max(1, int(CANVAS_H * s))
        view = self._preview_full_image.resize((dw, dh), Image.LANCZOS)
        photo = ImageTk.PhotoImage(view)
        self._preview_img_ref = photo
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(self.preview_pan_x, self.preview_pan_y, anchor="nw", image=photo)
        self._draw_selection_overlay()

    def _draw_selection_overlay(self):
        if not self.selected_element:
            return
        bbox = (self._preview_layout.get("elements") or {}).get(self.selected_element)
        if not bbox:
            return
        x0, y0 = self._world_to_canvas(bbox[0], bbox[1])
        x1, y1 = self._world_to_canvas(bbox[2], bbox[3])
        self.preview_canvas.create_rectangle(x0, y0, x1, y1, outline="#f9e2af", width=2, dash=(6, 4))
        if self.selected_element == "card":
            self.preview_canvas.create_line(x0, y0, x1, y0, fill="#a6e3a1", width=2)
            self.preview_canvas.create_line(x0, y1, x1, y1, fill="#a6e3a1", width=2)
            self.preview_canvas.create_line(x0, y0, x0, y1, fill="#a6e3a1", width=2)
            self.preview_canvas.create_line(x1, y0, x1, y1, fill="#a6e3a1", width=2)

    def _on_right_frame_resize(self, event):
        available_w = max(280, event.width - 16)
        available_h = max(340, event.height - 120)
        self.preview_canvas.configure(width=available_w, height=available_h)

        old_scale = self._effective_scale()
        cx = available_w / 2
        cy = available_h / 2
        wx = (cx - self.preview_pan_x) / old_scale if old_scale > 0 else CANVAS_W / 2
        wy = (cy - self.preview_pan_y) / old_scale if old_scale > 0 else CANVAS_H / 2

        self.preview_base_scale = min(available_w / CANVAS_W, available_h / CANVAS_H)
        ns = self._effective_scale()
        self.preview_pan_x = cx - wx * ns
        self.preview_pan_y = cy - wy * ns
        self._refresh_preview_canvas()

    def _hit_element(self, wx: float, wy: float) -> str | None:
        boxes = (self._preview_layout.get("elements") or {})
        for name in ("title", "author", "subtitle", "circle", "body", "card"):
            box = boxes.get(name)
            if not box:
                continue
            x0, y0, x1, y1 = box
            if x0 <= wx <= x1 and y0 <= wy <= y1:
                return name
        return None

    def _hit_card_edge(self, wx: float, wy: float) -> str | None:
        box = (self._preview_layout.get("elements") or {}).get("card")
        if not box:
            return None
        x0, y0, x1, y1 = box
        tol = max(6.0, 12.0 / self._effective_scale())
        if abs(wx - x0) <= tol and y0 - tol <= wy <= y1 + tol:
            return "left"
        if abs(wx - x1) <= tol and y0 - tol <= wy <= y1 + tol:
            return "right"
        if abs(wy - y0) <= tol and x0 - tol <= wx <= x1 + tol:
            return "top"
        if abs(wy - y1) <= tol and x0 - tol <= wx <= x1 + tol:
            return "bottom"
        return None

    def _set_selected(self, name: str | None):
        self.selected_element = name
        self.selected_label.config(text=f"Selected: {name if name else 'none'}")

    def _on_preview_mousewheel(self, event, delta_override=None):
        if self._preview_full_image is None:
            return
        delta = delta_override if delta_override is not None else event.delta
        if delta == 0:
            return
        wx, wy = self._canvas_to_world(event.x, event.y)
        step = 1.1 if delta > 0 else (1.0 / 1.1)
        new_zoom = max(self.preview_zoom_min, min(self.preview_zoom_max, self.preview_user_zoom * step))
        if abs(new_zoom - self.preview_user_zoom) < 1e-6:
            return
        self.preview_user_zoom = new_zoom
        ns = self._effective_scale()
        self.preview_pan_x = event.x - wx * ns
        self.preview_pan_y = event.y - wy * ns
        self._refresh_preview_canvas()

    def _on_preview_press(self, event):
        if self._preview_full_image is None:
            return
        self._drag_last = (event.x, event.y)
        wx, wy = self._canvas_to_world(event.x, event.y)
        edge = self._hit_card_edge(wx, wy)
        if edge:
            self._drag_mode = "resize_card"
            self._active_edge = edge
            self._set_selected("card")
            self._refresh_preview_canvas()
            return
        element = self._hit_element(wx, wy)
        if element:
            self._set_selected(element)
            self._drag_mode = "move_card" if element == "card" else "move_element"
            self._active_edge = None
        else:
            self._set_selected(None)
            self._drag_mode = "pan"
            self._active_edge = None
        self._refresh_preview_canvas()

    def _apply_card_padding(self, left, top, right, bottom, delay_ms=25):
        min_w = 220
        min_h = 260
        left = int(round(left))
        top = int(round(top))
        right = int(round(right))
        bottom = int(round(bottom))
        left = max(0, min(left, CANVAS_W - right - min_w))
        right = max(0, min(right, CANVAS_W - left - min_w))
        top = max(0, min(top, CANVAS_H - bottom - min_h))
        bottom = max(0, min(bottom, CANVAS_H - top - min_h))
        self.card_left_var.set(left)
        self.card_top_var.set(top)
        self.card_right_var.set(right)
        self.card_bottom_var.set(bottom)
        self._schedule_preview(delay_ms=delay_ms)

    def _on_preview_drag(self, event):
        if self._preview_full_image is None or not self._drag_mode:
            return
        last_x, last_y = self._drag_last
        dx_screen = event.x - last_x
        dy_screen = event.y - last_y
        self._drag_last = (event.x, event.y)

        if self._drag_mode == "pan":
            self.preview_pan_x += dx_screen
            self.preview_pan_y += dy_screen
            self._refresh_preview_canvas()
            return

        scale = self._effective_scale()
        dx_world = dx_screen / scale
        dy_world = dy_screen / scale

        if self._drag_mode == "move_element" and self.selected_element in self.layout_state["element_offsets"]:
            offset = self.layout_state["element_offsets"][self.selected_element]
            offset[0] += int(round(dx_world))
            offset[1] += int(round(dy_world))
            self._schedule_preview(delay_ms=25)
            return

        if self._drag_mode == "move_card":
            left = self.card_left_var.get() + dx_world
            right = self.card_right_var.get() - dx_world
            top = self.card_top_var.get() + dy_world
            bottom = self.card_bottom_var.get() - dy_world
            self._apply_card_padding(left, top, right, bottom, delay_ms=25)
            return

        if self._drag_mode == "resize_card":
            left = self.card_left_var.get()
            right = self.card_right_var.get()
            top = self.card_top_var.get()
            bottom = self.card_bottom_var.get()
            if self._active_edge == "left":
                left += dx_world
            elif self._active_edge == "right":
                right -= dx_world
            elif self._active_edge == "top":
                top += dy_world
            elif self._active_edge == "bottom":
                bottom -= dy_world
            self._apply_card_padding(left, top, right, bottom, delay_ms=25)

    def _on_preview_release(self, _event):
        self._drag_mode = None
        self._active_edge = None
        self._schedule_preview(delay_ms=10)

    def _on_preview_motion(self, event):
        if self._drag_mode:
            return
        wx, wy = self._canvas_to_world(event.x, event.y)
        edge = self._hit_card_edge(wx, wy)
        if edge in ("left", "right"):
            self.preview_canvas.configure(cursor="sb_h_double_arrow")
            return
        if edge in ("top", "bottom"):
            self.preview_canvas.configure(cursor="sb_v_double_arrow")
            return
        elem = self._hit_element(wx, wy)
        self.preview_canvas.configure(cursor="hand2" if elem else "arrow")

    def _scaled_params_for_canvas(self, params: dict, out_w: int, out_h: int) -> tuple[dict, int]:
        sx = out_w / CANVAS_W
        sy = out_h / CANVAS_H
        sf = min(sx, sy)
        scaled = dict(params)
        scaled["card_rect"] = (
            int(round(params["card_rect"][0] * sx)),
            int(round(params["card_rect"][1] * sy)),
            int(round(params["card_rect"][2] * sx)),
            int(round(params["card_rect"][3] * sy)),
        )
        scaled["padding"] = int(round(params["padding"] * sf))
        ps = params.get("padding_sides", {})
        scaled["padding_sides"] = {
            "left": int(round(ps.get("left", params["padding"]) * sx)),
            "right": int(round(ps.get("right", params["padding"]) * sx)),
            "top": int(round(ps.get("top", params["padding"]) * sy)),
            "bottom": int(round(ps.get("bottom", params["padding"]) * sy)),
        }
        for key in ("title_size", "author_size", "subtitle_size", "body_size"):
            scaled[key] = int(round(params[key] * sf))
        offs = params.get("element_offsets", {})
        scaled["element_offsets"] = {n: (int(round(v[0] * sx)), int(round(v[1] * sy))) for n, v in offs.items()}
        circle_d = max(24, int(round(CIRCLE_IMG_DIAM * sf)))
        return scaled, circle_d

    def _export_image(self):
        fmt = self.export_format_var.get().upper()
        ext_map = {"PNG": ".png", "JPG": ".jpg", "WEBP": ".webp"}
        ext = ext_map.get(fmt, ".png")
        path = filedialog.asksaveasfilename(
            title="Save image as...",
            defaultextension=ext,
            filetypes=[(fmt, f"*{ext}"), ("All", "*.*")],
            initialfile=f"poem_image{ext}",
        )
        if not path:
            return

        params = self._build_params()
        if self.web_opt_var.get():
            out_w, out_h = [int(x) for x in self.web_size_var.get().lower().split("x")]
        else:
            scale = int(self.export_scale_var.get())
            out_w, out_h = CANVAS_W * scale, CANVAS_H * scale

        scaled_params, circle_d = self._scaled_params_for_canvas(params, out_w, out_h)
        img = render_image(scaled_params, canvas_size=(out_w, out_h), circle_diameter=circle_d)
        if self.web_opt_var.get():
            clean = Image.new("RGB", img.size, (255, 255, 255))
            clean.paste(img)
            img = clean

        ext_lower = os.path.splitext(path)[1].lower()
        if ext_lower == "":
            path = path + ext
            ext_lower = ext

        try:
            if fmt == "JPG" or ext_lower in (".jpg", ".jpeg"):
                out = img.convert("RGB")
                if self.web_opt_var.get():
                    out.save(path, "JPEG", quality=85, optimize=True, progressive=True)
                else:
                    out.save(path, "JPEG", quality=95, dpi=(300, 300))
            elif fmt == "WEBP" or ext_lower == ".webp":
                out = img.convert("RGB")
                q = 85 if self.web_opt_var.get() else 92
                out.save(path, "WEBP", quality=q, method=6)
            else:
                if self.web_opt_var.get():
                    img.save(path, "PNG", optimize=True)
                else:
                    img.save(path, "PNG", dpi=(300, 300))
        except Exception as exc:
            messagebox.showerror("Export Error", f"Could not save image:\n{exc}")
            return

        messagebox.showinfo("Saved", f"Image saved to:\n{path}\n\nSize: {img.size[0]}x{img.size[1]} px")


if __name__ == "__main__":
    app = PoemImageApp()

    screen_w = app.winfo_screenwidth()
    screen_h = app.winfo_screenheight()
    start_w = min(1400, max(1100, int(screen_w * 0.9)))
    start_h = min(900, max(680, int(screen_h * 0.9)))
    pos_x = max(0, (screen_w - start_w) // 2)
    pos_y = max(0, (screen_h - start_h) // 2)

    app.minsize(980, 680)
    app.geometry(f"{start_w}x{start_h}+{pos_x}+{pos_y}")
    app.after(400, app._schedule_preview)
    app.mainloop()
