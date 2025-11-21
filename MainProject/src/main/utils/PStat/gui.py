from tkinter import *

if __name__ == "__main__":
    root = Tk()
    root.configure(bg="light green")
    root.title("Simple Calculator")
    root.geometry("270x150")

    display = StringVar()
    entry = Entry(root, textvariable=display)
    entry.grid(columnspan=4, ipadx=70)