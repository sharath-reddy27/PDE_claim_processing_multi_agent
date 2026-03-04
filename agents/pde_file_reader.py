import csv ,os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PDE_FILE = os.path.join(BASE, "data", "pde_flat_file.csv")

def read_pde_file():
    if not os.path.exists(PDE_FILE):
        raise FileNotFoundError(f"PDE file not found : {PDE_FILE}")
    with open(PDE_FILE, newline="",
    encoding="utf-8") as f:
        return list(csv.DictReader(f))
