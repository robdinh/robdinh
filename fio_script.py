import os
import time
import subprocess

def precondition():
	#Sequential write fill the disk at 2x capacity
	print("***Pre-conditioning device***\n")
	conditioning = "sudo fio --name=conditioning-fio --filename="+str(block_device)+" --bs=128k --ioengine=libaio --iodepth=4 --size=100% --loop=2 --direct=1 --rw=write --numjobs=32 --group_reporting --allow_mounted_write=1 --runtime=600s --time_based"
	output = subprocess.check_output(conditioning, shell=True)

def steady_state(measure, round, ss_condition, x=[], y=[], xx=[], xy=[], y_trend_list=[]):
	# Using values for rounds and measurements as lists to calculate line of best fit
	x.append(round)
	y.append(measure)
	xx.append(round * round)
	xy.append(round * measure)
	
	# Calculate line of best fit after 5 rounds
	if round >= 5:
		a = (sum(y[-5:]) * sum(xx[-5:]) - sum(x[-5:]) * sum(xy[-5:])) / (len(x[-5:]) * sum(xx[-5:]) - sum(x[-5:]) * sum(x[-5:]))
		b = (len(y[-5:]) * sum(xy[-5:]) - sum(x[-5:]) * sum(y[-5:])) / (len(x[-5:]) * sum(xx[-5:]) - sum(x[-5:]) * sum(x[-5:]))
		y_trend = a + b * round
	
		y_trend_list.append(y_trend)
		y_trend_range = max(y_trend_list[-5:]) - min(y_trend_list[-5:])
		y_range = max(y[-5:]) - min(y[-5:])
		y_average = sum(y[-5:]) / len(y[-5:])
		
		# Steady-state conditions
		if y_range < 0.2 * y_average and y_trend_range < 0.1 * y_average:
			ss_condition = True

	return ss_condition
	
def test(rwmixread_list, bs_list, iodepth, rw, jobname):
	precondition()
	print("***Transitioning device to steady-state***\n")
	ss_condition = False
	round = 0

	f = open(disk_model + "-" + time.strftime("%y%m%d") + "-fio.csv", "a+")
	
	while ss_condition == False and round < 25:	
		round = round + 1
		for rwmixread in (rwmixread_list):
			for bs in (bs_list):
				numjobs = 1 # Number of threads
				iops = 0.0
				bw = 0.0
				clat = 0.0
				qos = [0.0 for i in range(17)]

				command = "sudo fio --minimal --unified_rw_reporting=1 --name="+jobname+"-fio --filename="+str(block_device)+" --bs="+bs+" --ioengine=libaio --iodepth="+str(iodepth)+" --size=1G --direct=1 --rw="+rw+" --rwmixread="+str(rwmixread)+" --numjobs=1 --runtime=60s --time_based --group_reporting --allow_mounted_write=1 --refill_buffers --norandommap --randrepeat=0"
				os.system("sleep 2") #Give time to finish inflight IOs
				output = subprocess.check_output(command, shell=True)

				result = str(disk_model) + ";" + jobname + ";" + str(round) + ";" + str(rwmixread) + ";" + bs + ";" + str(numjobs) + ";" + str(iodepth)
												
				iops = iops + float(output.split(";")[fio_iops_pos])
				bw = bw + float(output.split(";")[fio_bw_pos])
				clat = clat + float(output.split(";")[fio_clat_pos])
				for j in range (0, 17):
					qos[j] = qos[j] + float(output.split(";")[fio_qos_pos_start+j][11:])

				result = result + ";" + str(iops) + ";" + str(bw) + ";" + str(clat)		
				for i in range (0, 17):
					result = result + ";" + str(qos[i])
								
				print (result)
				f.write(result+"\n")
				f.flush()

				#IOPS steady-state check measuring RND Write at 4k bs 
				if jobname == "iops" and rwmixread == 0 and bs == '4k':
					ss_condition = steady_state(iops, round, ss_condition)
		
				#Latency steady-state check measuring RND Write at 4k bs
				elif jobname == "clat" and rwmixread == 0 and bs == '4k':
					ss_condition = steady_state(clat, round, ss_condition)
					
	return f

disk_model= raw_input("Enter disk model: ")
block_device= raw_input("Enter block device to test: ")

# fio --minimal hardcoded positions of iops and read latencies
fio_iops_pos=7
fio_bw_pos=6
fio_clat_pos=15
fio_qos_pos_start=17

columns="disk;jobname;round;rwmixread;bs;numjobs;iodepth;iops;bandwidth;clatmean;p1;p5;p10;p20;p30;p40;p50;p60;p70;p80;p90;p95;p99;p995;p999;p9995;p9999"
f = open(disk_model + "-" + time.strftime("%y%m%d") + "-fio.csv", "w+")
f.write(columns+"\n")
	
# IOPS testing - random			
test([0, 70, 100], ['16k', '8k', '4k'], 32, 'randrw', 'iops')

# IOPS testing - sequential
test([0, 70, 100], ['16k', '8k', '4k'], 32, 'rw', 'iops')
				
# Latency testing
test([0, 70, 100], ['8k', '4k'], 1, 'randrw', 'clat')
				
f.closed