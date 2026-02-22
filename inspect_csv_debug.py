
import pandas as pd
import os

files = [
    r"C:\Users\yjham\Desktop\경제 study\잔고_미국 260218.csv",
    r"C:\Users\yjham\Desktop\경제 study\거래내역250301260218 - 한국시장.csv",
    r"C:\Users\yjham\Desktop\경제 study\거래내역250301260218 - 미국시장.csv"
]

def inspect(path):
    print(f"\n--- Inspecting: {os.path.basename(path)} ---")
    if not os.path.exists(path):
        print("File not found.")
        return

    try:
        # Try reading first few lines to see if there's metadata
        with open(path, 'r', encoding='cp949') as f:
            for i in range(5):
                print(f"Line {i}: {f.readline().strip()}")
        
        # Try pandas with skipping rows if needed
        # Assuming header might be on line 0 or 1
        df = pd.read_csv(path, encoding='cp949')
        print("Columns (Header=0):", df.columns.tolist())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    for f in files:
        inspect(f)
