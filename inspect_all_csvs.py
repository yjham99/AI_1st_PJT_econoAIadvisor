import glob
import os

def inspect():
    for f in glob.glob("*.csv"):
        print(f"\n--- {f} ---")
        try:
            with open(f, 'r', encoding='euc-kr') as file:
                for i in range(5):
                    line = file.readline()
                    if not line: break
                    print(f"{i}: {line.strip()[:100]}")
        except Exception as e:
            print(f"Error reading {f}: {e}")

if __name__ == '__main__':
    inspect()
