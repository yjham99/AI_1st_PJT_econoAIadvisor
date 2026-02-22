
import os

files = [
    r"C:\Users\yjham\Desktop\경제 study\잔고_국내260218.csv",
    r"C:\Users\yjham\Desktop\경제 study\잔고_미국 260218.csv",
    r"C:\Users\yjham\Desktop\경제 study\거래내역250301260218 - 한국시장.csv",
    r"C:\Users\yjham\Desktop\경제 study\거래내역250301260218 - 미국시장.csv"
]

def inspect_raw(path):
    print(f"\n--- Inspecting Raw: {os.path.basename(path)} ---")
    if not os.path.exists(path):
        print("File not found.")
        return

    encodings = ['cp949', 'utf-8', 'euc-kr']
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc) as f:
                print(f"Reading with {enc}...")
                for i in range(10):
                    line = f.readline()
                    if not line: break
                    print(f"Line {i}: {line.strip()}")
            return
        except Exception:
            continue
    print("Failed to read raw lines.")

if __name__ == "__main__":
    for f in files:
        inspect_raw(f)
