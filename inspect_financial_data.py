import os
import glob
import pandas as pd
import io

def main():
    with open("inspection_result.txt", "w", encoding="utf-8") as outfile:
        def log(msg):
            print(msg)
            outfile.write(msg + "\n")

        target_files = [
            # Portfolio
            "잔고_국내260218.csv",
            "잔고_미국 260218.csv",
            
            # Transactions
            "거래내역250301260218 - 한국시장.csv",
            "거래내역250301260218 - 미국시장.csv",
            
            # Market Data (Latest available)
            "260213 기관 매수상위(0209-0213) 코스피.csv",
            "260213 기관 매도상위(0209-0213) 코스피.csv",
            "260213 외국인 매수상위(0209-0213).csv"
        ]

        for fname in target_files:
            log(f"\n{'='*80}")
            log(f"FILE: {fname}")
            log(f"{'='*80}")
            
            if not os.path.exists(fname):
                log(f"File not found: {fname}")
                continue

            # Try reading with different encodings
            encodings = ['euc-kr', 'cp949', 'utf-8-sig', 'utf-8']
            success = False
            
            for enc in encodings:
                try:
                    # Read first few lines to inspect raw content
                    with open(fname, 'r', encoding=enc) as f:
                        head = [next(f) for _ in range(5)]
                    
                    log(f"Successfully read with encoding: {enc}")
                    log("-" * 40)
                    for line in head:
                        log(line.strip()[:150]) # Print first 150 chars
                    log("-" * 40)
                    
                    # Try parsing with pandas to see columns
                    try:
                        # Skip rows if needed - adjust based on raw output
                        df = pd.read_csv(fname, encoding=enc, nrows=2)
                        log("\nPandas Columns:")
                        log(str(df.columns.tolist()))
                    except Exception as e:
                        log(f"Pandas parse error: {e}")
                        
                    success = True
                    break # Success, move to next file
                    
                except StopIteration:
                     log(f"File {fname} is empty.")
                     break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    log(f"Error reading {fname}: {e}")
                    pass

            if not success:
                log("Failed to read file with any standard encoding.")

if __name__ == "__main__":
    main()
