# Imports
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont, ImageTk
import textwrap
import os

CANVAS_SIZE = (1200, 1600)
MARGIN = 120
TEXT_COLOR = (0, 0, 0)

bg_path = None
circle_path = None
font_path = None



def create_circular_image(image_path, size):
    img = Image.open(image_path).convert("RGBA")
    img = img.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)

    img.putalpha(mask)
    return img



def generate_image():
    if not bg_path or not circle_path or not font_path:
        messagebox.showerror("Missing files", "Please select background, circle image and font.")
        return

    title = title_entry.get()
    author = author_entry.get()
    roman = roman_entry.get()
    poem = poem_text.get("1.0", tk.END).strip()

    title_size = int(title_size_slider.get())
    body_size = int(body_size_slider.get())

    canvas = Image.new("RGB", CANVAS_SIZE, "white")
    draw = ImageDraw.Draw(canvas)

    bg = Image.open(bg_path).resize(CANVAS_SIZE)
    canvas.paste(bg, (0, 0))

    paper = Image.new(
        "RGB",
        (CANVAS_SIZE[0] - 2 * MARGIN, CANVAS_SIZE[1] - 2 * MARGIN),
        "white"
    )
    canvas.paste(paper, (MARGIN, MARGIN))

    title_font = ImageFont.truetype(font_path, title_size)
    body_font = ImageFont.truetype(font_path, body_size)
    roman_font = ImageFont.truetype(font_path, title_size - 10)

    draw.text((MARGIN + 40, MARGIN + 30), title, font=title_font, fill=TEXT_COLOR)
    draw.text((CANVAS_SIZE[0] - MARGIN - 300, MARGIN + 30), author, font=title_font, fill=TEXT_COLOR)
    draw.text((CANVAS_SIZE[0] // 2 - 30, MARGIN + 120), roman, font=roman_font, fill=TEXT_COLOR)

    circle = create_circular_image(circle_path, 180)
    canvas.paste(circle, (CANVAS_SIZE[0] // 2 - 90, MARGIN + 180), circle)

    y_text = MARGIN + 400
    x_text = MARGIN + 80

    for paragraph in poem.split("\n\n"):
        wrapped = textwrap.fill(paragraph, width=50)
        for line in wrapped.split("\n"):
            draw.text((x_text, y_text), line, font=body_font, fill=TEXT_COLOR)
            y_text += body_size + 8
        y_text += body_size

    os.makedirs("output", exist_ok=True)
    output_path = "output/poem_card.png"
    canvas.save(output_path)

    preview(canvas)
    messagebox.showinfo("Success", f"Image saved to {output_path}")



def preview(img):
    img_small = img.resize((300, 400))
    img_tk = ImageTk.PhotoImage(img_small)
    preview_label.config(image=img_tk)
    preview_label.image = img_tk



def select_bg():
    global bg_path
    bg_path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
    bg_label.config(text=os.path.basename(bg_path))



def select_circle():
    global circle_path
    circle_path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
    circle_label.config(text=os.path.basename(circle_path))



def select_font():
    global font_path
    font_path = filedialog.askopenfilename(filetypes=[("Fonts", "*.ttf")])
    font_label.config(text=os.path.basename(font_path))


# UI
root = tk.Tk()
root.title("Poetry Card Generator")
root.geometry("900x700")

left = tk.Frame(root)
left.pack(side="left", padx=10, pady=10)

right = tk.Frame(root)
right.pack(side="right", padx=10)

tk.Label(left, text="Title").pack(anchor="w")
title_entry = tk.Entry(left, width=40)
title_entry.insert(0, "Cien sonetos de amor")
title_entry.pack()

tk.Label(left, text="Author").pack(anchor="w")
author_entry = tk.Entry(left, width=40)
author_entry.insert(0, "Pablo Neruda")
author_entry.pack()

tk.Label(left, text="Roman numeral").pack(anchor="w")
roman_entry = tk.Entry(left, width=10)
roman_entry.insert(0, "XLIV")
roman_entry.pack()

tk.Label(left, text="Poem text").pack(anchor="w")
poem_text = tk.Text(left, width=50, height=15)
poem_text.pack()

tk.Label(left, text="Title size").pack(anchor="w")
title_size_slider = tk.Scale(left, from_=30, to=80, orient="horizontal")
title_size_slider.set(48)
title_size_slider.pack(fill="x")

tk.Label(left, text="Body size").pack(anchor="w")
body_size_slider = tk.Scale(left, from_=20, to=50, orient="horizontal")
body_size_slider.set(34)
body_size_slider.pack(fill="x")

tk.Button(left, text="Select background image", command=select_bg).pack(fill="x", pady=2)
bg_label = tk.Label(left, text="None")
bg_label.pack(anchor="w")

tk.Button(left, text="Select circle image", command=select_circle).pack(fill="x", pady=2)
circle_label = tk.Label(left, text="None")
circle_label.pack(anchor="w")

tk.Button(left, text="Select font (.ttf)", command=select_font).pack(fill="x", pady=2)
font_label = tk.Label(left, text="None")
font_label.pack(anchor="w")

tk.Button(left, text="Generate image", command=generate_image, bg="#333", fg="white").pack(fill="x", pady=10)

preview_label = tk.Label(right)
preview_label.pack()

root.mainloop()
