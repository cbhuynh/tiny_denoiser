# The script takes the calibration samples and
# returns the quantization ranges of the TinyDenoiser models 
# using the NNtool APIs

import numpy as np
import librosa
import sys, os

#import nntool APIs
from nntool.execution.graph_executer import GraphExecuter
from nntool.stats.activation_ranges_collector import ActivationRangesCollector

import pickle


# input variables
quant_sample_path = sys.argv[1]
quantization_bits = sys.argv[2]
gru = int(sys.argv[3])
h_state_len = int(sys.argv[5])

print(gru)

path_model_build = sys.argv[4]
print(path_model_build)

if gru == 1:
	print('This is a GRU-based model')
else:
	print('This is a LSTM-based model')



quantization_file = path_model_build + "data_quant.json"
if os.path.isfile(quantization_file):
	print("Quantization file is already here!")
	exit()

print("Going to collect the quantization stats and store into: " + quantization_file)
print('The calibration samples are taken from: ', quant_sample_path)

# parameters
SR = 16000
use_ema = False
lstm_hidden_states = h_state_len

# defines
executer = GraphExecuter(G, qrecs=None)

stats_collector = ActivationRangesCollector(use_ema=use_ema)
G.quantization = None



for filename in os.listdir(quant_sample_path):
	input_file = quant_sample_path + filename
	data, _ = librosa.load(input_file, sr=SR)
	stft = librosa.stft(data, n_fft=512, hop_length=100, win_length=400, 
		window='hann', center=False )
	rstft = np.abs(stft)
	len_seq = rstft.shape[1]

	#init lstm to zeros
	lstm_0_i_state = np.zeros(lstm_hidden_states)
	lstm_1_i_state = np.zeros(lstm_hidden_states)
	lstm_0_c_state = np.zeros(lstm_hidden_states)
	lstm_1_c_state = np.zeros(lstm_hidden_states)

	# debug stuff
	lim_0 = 0
	lim_1 = 0
	lim_2 = 0
	lim_3 = 0


	for i in range(len_seq): 
		single_mags = rstft[:,i]

		if gru == 1:
			data = [single_mags, lstm_0_i_state, lstm_1_i_state]
		else:
			data = [single_mags, lstm_0_i_state, lstm_0_c_state, lstm_1_i_state, lstm_1_c_state]

		stats_collector.collect_stats(G, data)
		outputs = executer.execute(data, qmode=None, silent=True)
		
		if gru == 1:
			lstm_0_i_state = outputs[G['GRU_74'].step_idx][0]
			lstm_1_i_state = outputs[G['GRU_136'].step_idx][0]
		else:
			lstm_0_i_state = outputs[G['LSTM_78'].step_idx][0]
			lstm_0_c_state = outputs[G['output_2'].step_idx][0]
			lstm_1_i_state = outputs[G['LSTM_144'].step_idx][0]
			lstm_1_c_state = outputs[G['output_3'].step_idx][0]
		
		print(lstm_0_i_state.shape)


		# debug monitor lstm state quantization
		if gru == 0:
			max_stats = np.max(np.abs(lstm_0_c_state))
			lim_1 = max_stats if max_stats > lim_1 else lim_1
			print('rnn_0_c_state | Sample: ',i,', Max: ', max_stats, 'Glob Max', lim_1)

			max_stats = np.max(np.abs(lstm_1_c_state))
			lim_3 = max_stats if max_stats > lim_3 else lim_3
			print('rnn_1_c_state | Sample: ',i,', Max: ', max_stats, 'Glob Max', lim_3)

		max_stats = np.max(np.abs(lstm_0_i_state))
		lim_0 = max_stats if max_stats > lim_0 else lim_0    
		print('rnn_0_i_state | Sample: ',i,', Max: ', max_stats, 'Glob Max', lim_0)

		max_stats = np.max(np.abs(lstm_1_i_state))
		lim_2 = max_stats if max_stats > lim_2 else lim_2   
		print('rnn_1_i_state | Sample: ',i,', Max: ', max_stats, 'Glob Max', lim_2)
	

# get quantization stas and dump to file
astats = stats_collector.stats
with open(quantization_file, 'wb') as fp:
    pickle.dump(astats, fp, protocol=pickle.HIGHEST_PROTOCOL)

