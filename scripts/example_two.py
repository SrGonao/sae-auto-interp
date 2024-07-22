import asyncio
import orjson

import torch

from sae_auto_interp.explainers import explanation_loader
from sae_auto_interp.scorers import RecallScorer
from sae_auto_interp.clients import Local
from sae_auto_interp.utils import load_tokenized_data, load_tokenizer, default_constructor
from sae_auto_interp.features import top_and_quantiles, FeatureLoader, FeatureDataset
from sae_auto_interp.pipeline import Pipe, Pipeline, Actor
from functools import partial

### Set directories ###

RAW_FEATURES_PATH = "raw_features"
EXPLAINER_OUT_DIR = "results/explanations/simple"
SCORER_OUT_DIR = "results/scores"
SCORER_OUT_DIR_B = "results/scores_b"

### Load dataset ###

tokenizer = load_tokenizer('gpt2')
tokens = load_tokenized_data(tokenizer)

modules = [".transformer.h.0", ".transformer.h.2"]
features = {
    m : torch.arange(1) for m in modules
}

dataset = FeatureDataset(
    raw_dir=RAW_FEATURES_PATH,
    modules = modules,
    features=features,
)

loader = FeatureLoader(
    tokens=tokens,
    dataset=dataset,
    constructor=default_constructor,
    sampler=top_and_quantiles
)

### Load client ###

client = Local("meta-llama/Meta-Llama-3-8B-Instruct")

### Build Explainer pipe ###

explainer_pipe = Pipe(
    Actor(
        partial(explanation_loader, explanation_dir=EXPLAINER_OUT_DIR)
    )
)

### Build Scorer pipe ###

def scorer_preprocess(result):
    record = result.record
    record.explanation = result.explanation
    return record

def scorer_postprocess(result):
    result = result.result()
    with open(f"{SCORER_OUT_DIR}/{result.record.feature}.txt", "wb") as f:
        f.write(orjson.dumps(result.score))

scorer_pipe = Pipe(
    Actor(
        RecallScorer(client, tokenizer=tokenizer),
        preprocess=scorer_preprocess,
        postprocess=scorer_postprocess
    )
)

### Build the pipeline ###

pipeline = Pipeline(
    loader.load,
    explainer_pipe,
    scorer_pipe,
)

asyncio.run(
    pipeline.run()
)
