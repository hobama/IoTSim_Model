# For single time power measurement in a serie
# The measurement will be triggered when the pin is high
# Stop when the pin return back to low
import sys
import os
import serial, select
import time
import signal
import datetime
import RPi.GPIO as GPIO

# Use pin 23 (BCM) to send the start signal to Arduino
GPIO.setmode(GPIO.BCM)
START_SIG_PIN = 12
GPIO.setup(START_SIG_PIN, GPIO.OUT)
GPIO.output(START_SIG_PIN, GPIO.LOW)
# Use pin 18 (BCM) to receive the end signal from Adruino
# Use internal pull-up resistor
END_SIG_PIN = 18
GPIO.setup(END_SIG_PIN, GPIO.IN) 

bSignaled = False
def signal_handler(signal, frame):
	global bSignaled
	print("You pressed Ctrl+C!")
	bSignaled = True
signal.signal(signal.SIGINT, signal_handler)

def log(f, string):
	if f is None:
		print(string)
	else:
		f.write(string)
		f.write("\n")
		

def get_time_milli():
	return (int)(time.time() * 1000)

out_filename = None
execution_time_in_ms = 3600 * 1000 

if len(sys.argv) == 2:
    out_filename = sys.argv[1]

def elapsed_time():
	global start_time
	return get_time_milli() - start_time


psu = serial.Serial("/dev/ttyUSB0", 9600, timeout=0.1)
psu.flush()
psu.flushInput()
psu.flushOutput()

psu.write("\r\n")
#time.sleep(1)
#psu.write("*IDN?\r\n")
#psu.write(":MEASure?\r\n")

psu.write(":HEAD OFF\r\n") # no header 

#psu.write(":DATAout:ITEM 2,0\r\n"); item = "current" # for current
#psu.write(":DATAout:ITEM 4,0\r\n"); item = "power" # for power
#psu.write(":DATAout:ITEM 1,0\r\n"); item = "volt" # for voltage
psu.write(":DATAout:ITEM 35,0\r\n"); item = "volt,curr,pf" # for more details
#psu.write(":DATAout:ITEM?\r\n")
#time.sleep(1)

#psu.write(":CURR:RANG 0.1\r\n") # Current range to minimum
#psu.write(":CURR:RANG 1.0\r\n") # Current range to minimum

if out_filename is not None:
	f = open(out_filename, "w")
else:
	f = None

extra_item_size = item.count(',')
if extra_item_size > 0:
	item += ",mul"

log(f, datetime.datetime.now().strftime("# %a %b %d %H:%M:%S %Y"))
log(f, "abstime,time_stamp," + item)

bNeedtoMeasure = True
ii = 0
data = ""
bTypeError = False

print("Start measurement...\r\n")
# send start signal to Arduino
start_time = get_time_milli()
GPIO.output(START_SIG_PIN, GPIO.HIGH)
# start power measurement
while True:
	if bNeedtoMeasure == True:
		psu.write(":MEAS?\r\n")
		bNeedtoMeasure = False
	try:
		a=psu.read()
	except serial.serialutil.SerialException:
		break
	except select.error, v:
		break

	try:
		data += "%c" % a
	except TypeError:
		bTypeError = True
		continue

	ii += 1
	if (ii == 12+11*extra_item_size):
		# +00.150E+3 or
		# +0122.9E+0;+058.93E-3;+00.487E+0
		if bTypeError == False:
			output_str = str(get_time_milli())
			output_str += "," + str(float(elapsed_time())/1000)

			sublist = data.split(";")
			vallist = []
			for subdata in sublist:
				idx = subdata.find("E")
				val = (float(subdata[:idx])) * (10 ** int(subdata[idx+1:]))
				vallist.append(val)
				output_str += "," + str(val)

			if extra_item_size > 0:
				mul = reduce(lambda x, y: x*y, vallist)
				output_str += "," + str(mul)
			log(f, output_str)

		ii = 0
		data = ""

		if bSignaled or elapsed_time() >= execution_time_in_ms:
			break
		if (GPIO.input(END_SIG_PIN) == 1): # if the trigger goes back to HIGH, end measurement
			break

		bTypeError = False
		bNeedtoMeasure = True
		continue

psu.close()
if f is not None:
	f.close()
GPIO.output(START_SIG_PIN, GPIO.LOW)
print("Measurement ends!\r\n")
