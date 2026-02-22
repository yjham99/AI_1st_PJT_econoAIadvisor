
import pandas as pd
import os

files = [
    r"C:\Users\yjham\Desktop\경제 study\잔고_국내260218.csv",
    r"C:\Users\yjham\Desktop\경제 study\잔고_미국 260218.csv",
    r"C:\Users\yjham\Desktop\경제 study\거래내역250301260218 - 한국시장.csv",
    r"C:\Users\yjham\Desktop\경제 study\거래내역250301260218 - 미국시장.csv"
]

def inspect(path):
    print(f"\n--- Inspecting: {os.path.basename(path)} ---")
    if not os.path.exists(path):
        print("File not found.")
        return

    encodings = ['utf-8', 'cp949', 'utf-8-sig', 'euc-kr']
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc)
            print(f"Success with {enc}")
            print(df.head(2).to_string())
            print("Columns:", df.columns.tolist())
            return
        except Exception as e:
            continue
    print("Failed to read with all attempted encodings.")

if __name__ == "__main__":
    for f in files:
        inspect(f)
