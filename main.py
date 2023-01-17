import os
import sys
import subprocess
import signal
import time
from datetime import datetime

DEPSPATH = "/home/deck/homebrew/plugins/decky-recorder/backend/out"
GSTPLUGINSPATH = DEPSPATH + "/gstreamer-1.0"
TMPLOCATION = "/tmp"

import logging
logging.basicConfig(filename="/tmp/decky-recorder.log",
					format='Decky Recorder: %(asctime)s %(levelname)s %(message)s',
					filemode='w+',
					force=True)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
std_out_file = open('/tmp/decky-recorder-std-out.log', 'w')
std_err_file = open('/tmp/decky-recorder-std-err.log', 'w')

class Plugin:

	_recording_process = None
	_mode = "localFile"
	_deckaudio = True
	_mic = False
	_filename = None

	async def start_recording(self):
		logger.info("Starting recording")
		if Plugin.is_recording(self) == True:
			logger.info("Error: Already recording")
			return

		os.environ["XDG_RUNTIME_DIR"] = "/run/user/1000"
		os.environ["XDG_SESSION_TYPE"] = "wayland"
		os.environ["HOME"] = "/home/deck"

		start_command = "GST_VAAPI_ALL_DRIVERS=1 GST_PLUGIN_PATH={} LD_LIBRARY_PATH={} gst-launch-1.0 -e -vvv".format(GSTPLUGINSPATH, DEPSPATH)

		videoPipeline = " pipewiresrc do-timestamp=true ! vaapipostproc ! queue ! vaapih264enc ! h264parse ! mp4mux name=sink !"

		cmd = start_command + videoPipeline
		if (self._mode == "localFile"):
			logger.info("Local File Recording")
			self._filename = datetime.now().strftime("%d-%m-%Y_%H-%M-%S") + ".mp4"
			# Heavily inspired by
			# https://git.sr.ht/~avery/recapture/tree/0fdbe014ec1f11bce386dc9468a760f8aed492e9/item/record.go#L19
			# https://git.sr.ht/~avery/recapture/tree/0fdbe014ec1f11bce386dc9468a760f8aed492e9/item/plugin/src/index.tsx#L161
			fileSinkPipeline = " filesink location={}/{}".format(TMPLOCATION, self._filename)
			cmd = cmd + fileSinkPipeline
		if (self._mode == "rtsp"):
			logger.info("RTSP-Server")
			return

		if (self._deckaudio or self._mic):
			adderPipeline = " adder name=audiomix ! audioconvert ! lamemp3enc target=bitrate bitrate=320 cbr=false ! sink.audio_0"
			cmd = cmd + adderPipeline

			if (self._deckaudio):
				monitor = subprocess.getoutput("pactl get-default-sink") + ".monitor"
				monitorPipeline = " pulsesrc device=\"{}\" ! audiorate ! audioconvert ! audiomix.".format(monitor)
				cmd = cmd + monitorPipeline
			if (self._mic):
				microphone = subprocess.getoutput("pactl get-default-source")
				microphonePipeline = " pulsesrc device=\"{}\" ! audiorate ! audioconvert ! audiomix.".format(microphone)
				cmd = cmd + microphonePipeline

		logger.info("Command: " + cmd)
		self._recording_process = subprocess.Popen(cmd, shell = True ,stdout = std_out_file, stderr = std_err_file)
		logger.info("Recording started!")
		return

	async def end_recording(self):
		logger.info("Stopping recording")
		if Plugin.is_recording(self) == False:
			logger.info("Error: No recording process to stop")
			return
		self._recording_process.send_signal(signal.SIGINT)
		self._recording_process.wait()
		time.sleep(10)
		self._recording_process = None
		logger.info("Recording stopped!")

		# if recording was a local file
		if (self._mode == "localFile"):
			logger.info("Repairing file")
			tmpFilePath = "{}/{}".format(TMPLOCATION, self._filename)
			permanent_location = "/home/deck/Videos/Decky-Recorder_{}".format(self._filename)
			self._filename = None
			ffmpegCmd = "ffmpeg -i {} -c copy {}".format(tmpFilePath, permanent_location)
			logger.info("Command: " + ffmpegCmd)
			ffmpeg = subprocess.Popen(ffmpegCmd, shell = True, stdout = std_out_file, stderr = std_err_file)
			ffmpeg.wait()
			logger.info("File repaired")
			os.remove(tmpFilePath)
			logger.info("Tmpfile deleted")
		return

	async def is_recording(self):
		logger.info("Is recording? " + str(self._recording_process is not None))
		return self._recording_process is not None

	async def set_current_mode(self, mode):
		logger.info("New mode: " + mode)
		self._mode = mode

	async def get_current_mode(self):
		logger.info("Current mode: " + self._mode)
		return self._mode

	async def set_deckaudio(self, deckaudio):
		logger.info("Set deck audio: " + str(deckaudio))
		self._deckaudio = deckaudio

	async def get_deckaudio(self):
		logger.info("Deck audio: " + str(self._deckaudio))
		return self._deckaudio

	async def set_mic(self, mic):
		logger.info("Set microphone: " + str(mic))
		self._mic = mic

	async def get_mic(self):
		logger.info("Microphone: " + str(self._mic))
		return self._mic

	async def get_wlan_ip(self):
		ip = subprocess.getoutput("ip -f inet addr show wlan0 | sed -En -e 's/.*inet ([0-9.]+).*/\\1/p'")
		logger.info("IP: " + ip)
		return ip

	def write_config(self):
		return

	async def _main(self):
		return

	async def _unload(self):
		if Plugin.is_recording(self) == True:
			Plugin.end_recording(self)
		return