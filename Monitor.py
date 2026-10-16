import csv
import time
from datetime import datetime

import matplotlib.pyplot as plt
import serial
import winsound


# Change this if Arduino IDE shows a different port.
PORT = "COM3"

BAUD_RATE = 115200
ALARM_TEMPERATURE_C = 22.0
RUN_SECONDS = 10 * 60  # 10 minutes


# Give this run unique filenames so it won't overwrite an earlier run.
file_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_name = f"room_log_{file_stamp}.csv"
graph_name = f"room_graph_{file_stamp}.png"

temperatures = []
humidities = []
elapsed_minutes = []
below_limit = []

print(f"Connecting to ESP32 on {PORT}...")
print("Keep the ESP32 connected and Arduino Serial Monitor closed.")

try:
    board = serial.Serial(PORT, BAUD_RATE, timeout=2)
except serial.SerialException as error:
    print(f"Could not open {PORT}: {error}")
    print("Check the USB cable, COM port, and that Serial Monitor is closed.")
    raise SystemExit

# Connecting can restart the ESP32. Wait for it to start sending data.
time.sleep(2)
board.reset_input_buffer()

start_clock = time.monotonic()
alarm_was_active = False

print("Recording for 10 minutes. Leave this program running.")
print(f"Data file: {csv_name}")

try:
    with open(csv_name, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)

        writer.writerow([
            "timestamp",
            "elapsed_minutes",
            "temperature_C",
            "humidity_percent",
            "below_22C",
        ])
        csv_file.flush()

        while time.monotonic() - start_clock < RUN_SECONDS:
            raw_line = board.readline()
            line = raw_line.decode("utf-8", errors="replace").strip()

            # Ignore messages that aren't two comma-separated numbers.
            pieces = line.split(",")
            if len(pieces) != 2:
                continue

            try:
                temperature = float(pieces[0])
                humidity = float(pieces[1])
            except ValueError:
                continue

            now = datetime.now()
            minutes = (time.monotonic() - start_clock) / 60
            is_cold = temperature < ALARM_TEMPERATURE_C

            temperatures.append(temperature)
            humidities.append(humidity)
            elapsed_minutes.append(minutes)
            below_limit.append(is_cold)

            writer.writerow([
                now.isoformat(timespec="seconds"),
                round(minutes, 2),
                temperature,
                humidity,
                is_cold,
            ])
            csv_file.flush()

            if is_cold:
                print(
                    f"{now.strftime('%H:%M:%S')}  "
                    f"{temperature:.1f} C  {humidity:.0f}% RH  "
                    "WARNING: below 22 C"
                )
            else:
                print(
                    f"{now.strftime('%H:%M:%S')}  "
                    f"{temperature:.1f} C  {humidity:.0f}% RH"
                )

            # Beep only when the temperature first crosses below 22 C.
            if is_cold and not alarm_was_active:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

            alarm_was_active = is_cold

except KeyboardInterrupt:
    print("\nStopped early. Making a report from readings collected so far.")

finally:
    board.close()


if not temperatures:
    print("No readings were received, so no graph was created.")
    print("Check the Arduino Serial Monitor for lines like 21.0,48.0.")
    raise SystemExit

# Make a temperature graph and a humidity graph.
figure, (temp_axis, humidity_axis) = plt.subplots(
    2, 1, figsize=(10, 7), sharex=True
)

temp_axis.plot(elapsed_minutes, temperatures, color="blue")
temp_axis.axhline(
    ALARM_TEMPERATURE_C,
    color="red",
    linestyle="--",
    label="22 C warning limit",
)

for minute, temperature, is_cold in zip(
    elapsed_minutes, temperatures, below_limit
):
    if is_cold:
        temp_axis.scatter(minute, temperature, color="red", s=25)

temp_axis.set_ylabel("Temperature (C)")
temp_axis.set_title("Room temperature and humidity")
temp_axis.grid(True)
temp_axis.legend()

humidity_axis.plot(elapsed_minutes, humidities, color="green")
humidity_axis.set_xlabel("Time since recording started (minutes)")
humidity_axis.set_ylabel("Humidity (%)")
humidity_axis.grid(True)

figure.tight_layout()
figure.savefig(graph_name, dpi=150)

print(f"\nCSV saved as: {csv_name}")
print(f"Graph saved as: {graph_name}")
print(f"Number of readings: {len(temperatures)}")
print(f"Lowest temperature: {min(temperatures):.1f} C")
print(f"Average temperature: {sum(temperatures) / len(temperatures):.1f} C")
print(f"Highest temperature: {max(temperatures):.1f} C")
print(f"Readings below 22 C: {sum(below_limit)}")

plt.show()