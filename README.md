# DSC180A-proj1-PD
Causal Inference for de-confounding popularity bias. This is a replicated project from [Causal Intervention for Leveraging Popularity Bias in
Recommendation](https://arxiv.org/pdf/2105.06067.pdf) based on Tensorflow. 

# Dataset Download
Douban(Movie): The original data is downloaded from the following link, cited as Song, Weiping, et al. "Session-based social recommendation via dynamic graph attention networks." WSDM 2019. Processed data is too large to be pushed so you may download it from the original authors' GitHub page.
[original data](https://github.com/DeepGraphLearning/RecommenderSystems/blob/master/socialRec/README.md#douban-data), [processed_data](https://github.com/zyang1580/PDA/tree/main/data/douban)

# Requirement 
tensorflow == 1.14 \
Cython (for neurec evaluator)\
Numpy\
prefetch-generator\
python3\
pandas == 0.25.0
