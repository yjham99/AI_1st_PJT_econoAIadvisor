
import os

files = [
    r"C:\Users\yjham\Desktop\경제 study\잔고_국내260218.csv",
    r"C:\Users\yjham\Desktop\경제 study\잔고_미국 260218.csv",
    r"C:\Users\yjham\Desktop\경제 study\거래내역250301260218 - 한국시장.csv",
    r"C:\Users\yjham\Desktop\경제 study\거래내역250301260218 - 미국시장.csv"
]

output_path = "head_inspection.txt"

with open(output_path, 'w', encoding='utf-8') as outfile:
    for path in files:
        outfile.write(f"\n[{os.path.basename(path)}]\n")
        if not os.path.exists(path):
            outfile.write("  -> File NOT FOUND\n")
            continue

        try:
            with open(path, 'r', encoding='cp949') as infile:
                for i in range(15):
                    line = infile.readline()
                    if not line: break
                    # repr() prevents control characters from messing up the output file
                    outfile.write(f"Line {i}: {repr(line.strip())}\n")
        except Exception as e:
            outfile.write(f"  -> Error reading: {e}\n")

print(f"Inspection written to {output_path}")
