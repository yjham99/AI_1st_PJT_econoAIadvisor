
import os

files = [
    r"C:\Users\yjham\Desktop\경제 study\잔고_국내260218.csv",
    r"C:\Users\yjham\Desktop\경제 study\잔고_미국 260218.csv",
    r"C:\Users\yjham\Desktop\경제 study\거래내역250301260218 - 한국시장.csv",
    r"C:\Users\yjham\Desktop\경제 study\거래내역250301260218 - 미국시장.csv"
]

def inspect_file(path):
    print(f"\n[{os.path.basename(path)}]")
    if not os.path.exists(path):
        print("  -> File NOT FOUND")
        return

    # 1. Read raw bytes to see BOM or encoding hints
    try:
        with open(path, 'rb') as f:
            raw_head = f.read(100)
            print(f"  -> First 100 bytes: {raw_head}")
    except Exception as e:
        print(f"  -> Error reading bytes: {e}")

    # 2. Try decoding with cp949 (common for KR CSVs via Excel)
    print("  -> Text lines (cp949):")
    try:
        with open(path, 'r', encoding='cp949') as f:
            for i in range(5):
                line = f.readline()
                if not line: break
                print(f"    Line {i}: {repr(line.strip())}")
    except Exception as e:
        print(f"    -> Decode Error: {e}")

if __name__ == "__main__":
    for f in files:
        inspect_file(f)
