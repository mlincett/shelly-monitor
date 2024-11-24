#!/usr/bin/env python3
import argparse
import requests
import time
import signal
import sys
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


class ShellyMonitor:
    def __init__(self, ip_address):
        self.ip = ip_address
        self.url = f"http://{ip_address}/status"
        self.data = []
        self.last_measurement = None
        self.intervals = []  # Will store number of samples between changes
        self.last_change_idx = None
        self.running = True
        self.sampling_period = 1.0  # seconds

        # Setup signal handler for graceful exit
        signal.signal(signal.SIGINT, self.handle_exit)

        # Create timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_file = f"shelly_power_{timestamp}.csv"
        self.plot_file = f"shelly_power_{timestamp}.png"
        self.analysis_file = f"shelly_analysis_{timestamp}.txt"

    def get_power(self):
        try:
            response = requests.get(self.url, timeout=2)
            response.raise_for_status()
            return response.json()["meters"][0]["power"]
        except Exception as e:
            print(f"Error reading power: {e}")
            return None

    def check_value_change(self, power, current_idx):
        if self.last_measurement is None:
            self.last_measurement = power
            self.last_change_idx = current_idx
            return

        if self.last_measurement != power:
            if self.last_change_idx is not None:  # Skip first interval
                interval_samples = current_idx - self.last_change_idx
                self.intervals.append(interval_samples)
            self.last_measurement = power
            self.last_change_idx = current_idx

    def handle_exit(self, signum, frame):
        print("\nStopping monitoring...")
        self.running = False

    def analyze_intervals(self):
        if len(self.intervals) < 2:  # Need at least 2 intervals for analysis
            return "Not enough data for analysis"

        # Remove the last interval as it might be incomplete
        intervals = self.intervals[:-1]

        if not intervals:
            return "Not enough intervals for analysis"

        analysis = []
        analysis.append(f"Total samples collected: {len(self.data)}")
        analysis.append(f"Number of value changes: {len(self.intervals)}")
        analysis.append("\nIntervals between value changes:")
        min_samples = min(intervals)
        avg_samples = sum(intervals) / len(intervals)
        max_samples = max(intervals)

        analysis.append(
            f"Minimum: {min_samples} samples ({min_samples * self.sampling_period:.1f} seconds)"
        )
        analysis.append(
            f"Average: {avg_samples:.1f} samples ({avg_samples * self.sampling_period:.1f} seconds)"
        )
        analysis.append(
            f"Maximum: {max_samples} samples ({max_samples * self.sampling_period:.1f} seconds)"
        )

        if min_samples >= 2:
            analysis.append(
                f"\nYou can safely increase the sampling interval to {self.sampling_period * 2:.1f} seconds"
            )
            analysis.append(
                f"(minimum interval between changes was {min_samples} samples)"
            )

        return "\n".join(analysis)

    def save_and_plot(self):
        if not self.data:
            print("No data collected!")
            return

        # Save to CSV
        df = pd.DataFrame(self.data, columns=["timestamp", "power"])
        df.to_csv(self.csv_file, index=False)
        print(f"\nData saved to {self.csv_file}")

        # Create power vs time plot
        plt.figure(figsize=(12, 6))
        plt.plot(df["timestamp"], df["power"])
        plt.title("Power Consumption Over Time")
        plt.xlabel("Time")
        plt.ylabel("Power (W)")
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(self.plot_file)
        plt.close()
        print(f"Plot saved to {self.plot_file}")

        # Save analysis
        analysis = self.analyze_intervals()
        with open(self.analysis_file, "w") as f:
            f.write(analysis)
        print(f"Analysis saved to {self.analysis_file}")
        print("\nAnalysis Summary:")
        print(analysis)

    def monitor(self):
        print(f"Monitoring Shelly Plug S at {self.ip}")
        print("Press CTRL+C to stop...")

        current_idx = 0
        while self.running:
            start_time = time.time()

            power = self.get_power()
            if power is not None:
                timestamp = datetime.now()
                self.data.append([timestamp, power])
                self.check_value_change(power, current_idx)
                print(
                    f"\rPower: {power:6.2f} W | Time: {timestamp.strftime('%H:%M:%S')} | "
                    f"Samples: {len(self.data)}",
                    end="",
                )
                current_idx += 1

            # Wait for remaining time to achieve 0.5s interval
            elapsed = time.time() - start_time
            sleep_time = max(0, self.sampling_period - elapsed)
            time.sleep(sleep_time)


def main():
    parser = argparse.ArgumentParser(
        description="Monitor Shelly Plug S power consumption"
    )
    parser.add_argument("ip", help="IP address of the Shelly Plug S")
    args = parser.parse_args()

    monitor = ShellyMonitor(args.ip)
    monitor.monitor()
    monitor.save_and_plot()


if __name__ == "__main__":
    main()
