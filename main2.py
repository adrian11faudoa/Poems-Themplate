# Imports
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageDraw, ImageFont, ImageTk
import textwrap
import os

CANVAS_SIZE = (1200, 1600)
MARGIN = 120
TEXT_COLOR = (0, 0, 0)

# Class Poem Card App
class PoemCardApp:
    def __init__(self, root):
        self.root = root
        root.title("Poetry Card Generator")

        self.bg_path = None
        self.circle_path = None
        self.font_path = "fonts/PlayfairDisplay-Regular.ttf"

        self.title_var = tk.StringVar(value="Cien sonetos de amor")
        self.author_var = tk.StringVar(value="Pablo Neruda")
        self.roman_var = tk.StringVar(value="XLIV")
        self.font_size_var = tk.IntVar(value=34)

        self.create_ui()
        self.preview_label = None

    # UI
    def create_ui(self):
        controls = tk.Frame(self.root)
        controls.pack(side="left", fill="y", padx=10)

        preview = tk.Frame(self.root)
        preview.pack(side="right", expand=True)

        tk.Button(controls, text="Load Background", command=self.load_bg).pack(fill="x")
        tk.Button(controls, text="Load Circle Image", command=self.load_circle).pack(fill="x")
        tk.Button(controls, text="Choose Font", command=self.choose_font).pack(fill="x")

        ttk.Label(controls, text="Book Title").pack()
        ttk.Entry(controls, textvariable=self.title_var).pack(fill="x")

        ttk.Label(controls, text="Author").pack()
        ttk.Entry(controls, textvariable=self.author_var).pack(fill="x")

        ttk.Label(controls, text="Roman Numeral").pack()
        ttk.Entry(controls, textvariable=self.roman_var).pack(fill="x")

        ttk.Label(controls, text="Poem Text").pack()
        self.poem_text = tk.Text(controls, height=15, wrap="word")
        self.poem_text.pack(fill="both")
        self.poem_text.insert("1.0",
            "Sabrás que no te amo y que te amo\n"
            "puesto que de dos modos es la vida,\n"
            "la palabra es un ala del silencio."
        )

        ttk.Label(controls, text="Font Size").pack()
        ttk.Scale(controls, from_=24, to=48, variable=self.font_size_var,
                  orient="horizontal").pack(fill="x")

        tk.Button(controls, text="Update Preview", command=self.render).pack(fill="x", pady=5)
        tk.Button(controls, text="Export Image", command=self.export).pack(fill="x")

        self.preview_canvas = tk.Label(preview)
        self.preview_canvas.pack(expand=True)

    def load_bg(self):
        self.bg_path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.png")])

    def load_circle(self):
        self.circle_path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.png")])

    def choose_font(self):
        self.font_path = filedialog.askopenfilename(filetypes=[("Fonts", "*.ttf")])

    def create_circle(self, path, size):
        img = Image.open(path).convert("RGBA").resize((size, size))
        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        img.putalpha(mask)
        return img

    def render(self):
        if not self.bg_path:
            return

        canvas = Image.new("RGB", CANVAS_SIZE, "white")
        draw = ImageDraw.Draw(canvas)

        bg = Image.open(self.bg_path).resize(CANVAS_SIZE)
        canvas.paste(bg, (0, 0))

        paper = Image.new("RGB",
            (CANVAS_SIZE[0]-2*MARGIN, CANVAS_SIZE[1]-2*MARGIN), "white")
        canvas.paste(paper, (MARGIN, MARGIN))

        title_font = ImageFont.truetype(self.font_path, 48)
        body_font = ImageFont.truetype(self.font_path, self.font_size_var.get())
        roman_font = ImageFont.truetype(self.font_path, 40)

        draw.text((MARGIN+40, MARGIN+30), self.title_var.get(), font=title_font, fill=TEXT_COLOR)
        draw.text((CANVAS_SIZE[0]-MARGIN-300, MARGIN+30),
                  self.author_var.get(), font=title_font, fill=TEXT_COLOR)

        draw.text((CANVAS_SIZE[0]//2-30, MARGIN+120),
                  self.roman_var.get(), font=roman_font, fill=TEXT_COLOR)

        if self.circle_path:
            circle = self.create_circle(self.circle_path, 180)
            canvas.paste(circle, (CANVAS_SIZE[0]//2-90, MARGIN+180), circle)

        text = self.poem_text.get("1.0", "end").strip()
        y = MARGIN + 420
        for line in textwrap.wrap(text, 55):
            draw.text((MARGIN+80, y), line, font=body_font, fill=TEXT_COLOR)
            y += body_font.size + 10

        self.preview_img = ImageTk.PhotoImage(canvas.resize((600, 800)))
        self.preview_canvas.configure(image=self.preview_img)
        self.rendered_image = canvas

    def export(self):
        if not hasattr(self, "rendered_image"):
            return
        os.makedirs("output", exist_ok=True)
        self.rendered_image.save("output/poem_card.png")

root = tk.Tk()
app = PoemCardApp(root)
root.mainloop()


