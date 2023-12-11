# DSC180A-proj1-PD
Causal Inference for de-confounding popularity bias. This is a replicated project from [Causal Intervention for Leveraging Popularity Bias in
Recommendation](https://arxiv.org/pdf/2105.06067.pdf) based on Tensorflow. 

# Dataset Download
Douban(Movie): The original data is downloaded from the following link, cited as Song, Weiping, et al. "Session-based social recommendation via dynamic graph attention networks." WSDM 2019. You can download processed data from douban.zip and remember to move the unzipped files into the main douban folder.
[original data](https://github.com/DeepGraphLearning/RecommenderSystems/blob/master/socialRec/README.md#douban-data), [processed_data](https://github.com/bettygong/DSC180A-proj1-PD/tree/main/data/douban)

# Requirement 
tensorflow == 1.14 \
Cython (for neurec evaluator)\
Numpy\
prefetch-generator\
python3\
pandas == 0.25.0

In order to set up the environment and control package versions, please download [environment.yml](https://github.com/bettygong/DSC180A-proj1-PD/blob/main/environment.yml) and create the environment `myenv` by entering `conda env create -f environment.yml` in the terminal. \
Then install employed packages in `myenv` by entering:\
pip install tensorflow==1.14 \
python -m pip install scipy \
pip install prefetch-generator \
pip install -U matplotlib \



