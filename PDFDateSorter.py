from tkinter import Tk, filedialog, Label, Button, Listbox, Scrollbar, Canvas, Frame, ttk, Text, END
import sqlite3
import os
import PyPDF2
import re
from natsort import natsorted

def initialize_database():
    conn = sqlite3.connect('pdf_analysis.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS documents 
              (filename TEXT, filepath TEXT, text_content TEXT, year TEXT, month TEXT, day TEXT)''')
    conn.commit()
    conn.close()

def ocr_and_store(folder_path):
    conn = sqlite3.connect('pdf_analysis.db')
    c = conn.cursor()
    for filename in os.listdir(folder_path):
        if filename.endswith('.pdf'):
            file_path = os.path.join(folder_path, filename)

            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text_content = ''
                for page_num in range(min(2, len(pdf_reader.pages))):
                    page = pdf_reader.pages[page_num]
                    text_content += page.extract_text()

            c.execute("INSERT INTO documents (filename, filepath, text_content) VALUES (?, ?, ?)",
                      (filename, file_path, text_content))
    conn.commit()
    conn.close()

    extract_dates()  # Automatically extract dates after OCR

def extract_dates():
    conn = sqlite3.connect('pdf_analysis.db')
    c = conn.cursor()
    c.execute("SELECT rowid, text_content FROM documents")
    rows = c.fetchall()

    date_patterns = [
        # Numerical day, month, year
        r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})',
        r'(\d{1,2})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{4})',
        r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})',

        # Word month, numerical day, year
        r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b)\s*(\d{1,2})\s*(\d{4})',
        r'(\d{1,2})\s*(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b)\s*(\d{4})',

        # Full word month, numerical day, year
        r'(\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b)\s*(\d{1,2})\s*(\d{4})',
        r'(\d{1,2})\s*(\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b)\s*(\d{4})',

        # Specific formats and textual contexts
        r'Sent\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*(\d{1})(\d{1})(\d{4})',
        r'Sent\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*(\d{1,2})\s*(\d{1,2})\s*(\d{4})',
        r'Date(?:\s+ofReport)?\s+(\d{1,2})\s*(?:\d*)\s*(\d{1,2})\s*(\d{4})',

        # Year first, then month and day
        r'(\d{4})\s*(\d{1,2})\s*(\d{1,2})',

        # With time stamps
        r'(\d{1,2})\s*(\d{1,2})\s*(\d{4})\s*\d{1,2}\:\d{1,2}',

        # Only digits without delimiter
        r'(\d{1,2})(\d{2})(\d{4})',

        # With leading/trailing spaces or lines
        r'(?:^|\s+)(\d{1,2})(\d{2})(\d{4})(?:\s+|$)',

        # Loose matching for "May 11 2022" format with optional spaces
        r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b)\s*[-,]?\s*(\d{1,2})\s*[-,]?\s*(\d{4})',
        r'(\d{1,2})\s*[-,]?\s*(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b)\s*[-,]?\s*(\d{4})',

        # General pattern to match "823 2022" type formats
        r'(\d{1,2})\s+(\d{1,2})\s+(\d{4})',

        # Special patterns for "Sent Thur" or other weekdays
        r'Sent\s*(?:Mon|Tue|Wed|Thu|Thur|Fri|Sat|Sun)?\s*(\d{1,2})\s*[-]?\s*(\d{1,2})\s*[-]?\s*(\d{4})',
        r'Sent\s*(?:Mon|Tue|Wed|Thu|Thur|Fri|Sat|Sun)?\s*([1-9])(\d{1,2})\s*(\d{4})',

        # Pattern for "512 2022" format
        r'(\d{1,2})\s+(\d{1,2})\s+(\d{4})',

        # Pattern for "Wednesday May 03 2023" format
        r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b)\s+(\d{1,2})\s+(\d{4})',

        # Pattern for "Monday May 01 2023 95433 AM" format
        r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b)\s+(\d{1,2})\s+(\d{4})\s+(\d{1,2}:\d{1,2}\d{1,2}\s+(?:AM|PM))',

        # Pattern for "Date Wednesday May 03 2023 43100 PM" format
        r'Date(?:\s+ofReport)?\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s+(\d{1,2})\s+(\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b)\s+(\d{1,2})\s+(\d{4})\s+(\d{1,2})(\d{2})(?:\s+AM|PM)',

        # Additional loose patterns
        r'(\d{1,2})\s*[-, \/]?\s*(\d{1,2})\s*[-, \/]?\s*(\d{4})',
    ]

    for row in rows:
        rowid, text_content = row
        possible_dates = []  # Store all possible dates for this row

        for pattern in date_patterns:
            dates = re.findall(pattern, text_content, re.IGNORECASE)
            if dates:
                for parts in dates:
                    if len(parts) == 3:  # Confirm that we have day, month, and year
                        month, day, year = parts
                        if year.isdigit() and 2000 <= int(year) <= 2023:
                            if day.isdigit() and 1 <= int(day) <= 31:
                                if month.isdigit() and 1 <= int(month) <= 12:
                                    possible_dates.append((day, month, year))

        # Decide on the "best" date to use
        if possible_dates:
            best_date = possible_dates[0]  # For now, just use the first found as the best
            c.execute("UPDATE documents SET day = ?, month = ?, year = ? WHERE rowid = ?", best_date + (rowid,))
        else:
            c.execute("UPDATE documents SET day = NULL, month = NULL, year = NULL WHERE rowid = ?", (rowid,))

    conn.commit()
    conn.close()



def display_database():
    # Create a new top-level window
    new_window = Tk()
    new_window.title('Database Content')
    new_window.geometry("1000x600")

    # Create a Frame
    frame = Frame(new_window)
    frame.pack(fill="both", expand=True)

    # Create a treeview in the frame
    tree = ttk.Treeview(frame, columns=('Filename', 'Year', 'Month', 'Day', 'OCR Snippet'), show='headings')
    tree.heading('Filename', text='Filename')
    tree.heading('Year', text='Year')
    tree.heading('Month', text='Month')
    tree.heading('Day', text='Day')
    tree.heading('OCR Snippet', text='OCR Snippet')
    tree.column('Filename', width=200)
    tree.column('Year', width=50)
    tree.column('Month', width=50)
    tree.column('Day', width=50)
    tree.column('OCR Snippet', width=400)
    tree.grid(row=0, column=0, sticky="nsew")

    # Scrollbar for Treeview
    scrollbar = Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=0, column=1, sticky="ns")

    # Create a Text widget below the Treeview to display full OCR text
    ocr_display = Text(new_window, wrap="none", height=10)
    ocr_display.pack(fill="both", expand=True)

    # Function to update the Text widget
    def update_ocr_display(event):
        item = tree.selection()[0]
        ocr_text = tree.item(item, 'values')[4]
        ocr_display.delete(1.0, "end")
        ocr_display.insert("end", ocr_text)

    tree.bind('<ButtonRelease-1>', update_ocr_display)

    # Fetch and populate the Treeview
    conn = sqlite3.connect('pdf_analysis.db')
    c = conn.cursor()
    c.execute("SELECT filename, year, month, day, text_content FROM documents")
    rows = c.fetchall()
    sorted_rows = natsorted(rows, key=lambda row: row[0])
    for row in sorted_rows:
        filename, year, month, day, text_content = row
        snippet = text_content[:100]  # Show the first 100 characters as a snippet
        tree.insert('', 'end', values=(filename, year, month, day, text_content))  # Note: I put the full text_content here

    conn.close()




def clear_database():
    conn = sqlite3.connect('pdf_analysis.db')
    c = conn.cursor()
    c.execute("DELETE FROM documents")
    conn.commit()
    conn.close()
    listbox.delete(0, END)

def select_folder():
    folder_path = filedialog.askdirectory()
    if folder_path:
        ocr_and_store(folder_path)
        display_database()

# Initialize the database
initialize_database()

# Tkinter GUI
root = Tk()
root.title('PDF Date Extractor')

listbox = Listbox(root, width=50, height=20)
listbox.pack(pady=20)

select_button = Button(root, text="Select Folder", command=select_folder)
select_button.pack(side="left", padx=10)

clear_button = Button(root, text="Clear Database", command=clear_database)
clear_button.pack(side="left", padx=10)

display_button = Button(root, text="Display Database", command=display_database)
display_button.pack(side="left", padx=10)

root.mainloop()
