import ray
from ray import train, tune
from ray.train import Checkpoint
from ray.tune.search.optuna import OptunaSearch
import os
from launch_training import *
import random


ray.init(
    _system_config={
        "object_spilling_config": json.dumps(
            {"type": "filesystem", "params": {"directory_path": "/home/nrubio/Desktop"}},
        )
    },
    num_cpus=1,
    num_gpus=3,
)

def objective(config):

    train_mse, val_mse, model_name = train_and_val_gnn(anatomy = "Aorta_rand", num_geos = 110, unsteady = True, unsteady_opt = False, loss_type = "dP", config = config)
    metric = val_mse

    train.report({"inference_performance": float(metric)})  # Report to Tune

def main():
    search_space = {
    "lr": tune.loguniform(1e-6, 1e-2),
    "lr_decay": tune.loguniform(1e-4, 1e-0),
    "batch_size": tune.randint(20, 40),
    "latent_size_mlp": tune.randint(30, 80),
    "hl_mlp": tune.randint(1, 3)}
    algo = OptunaSearch()

    objective_with_gpu = tune.with_resources(objective, {"gpu": 3})
    storage_path = os.path.expanduser("/home/nrubio/Desktop/junction_pressure_differentials/results/hyperparameter_optimization")
    exp_name = "aorta_unsteady"
    path = os.path.join(storage_path, exp_name)
    tuner = tune.Tuner(
        trainable = objective_with_gpu,
        tune_config=tune.TuneConfig(
            metric="inference_performance", mode="min", search_alg=algo,
            num_samples=500
            ),
        run_config=train.RunConfig(storage_path=storage_path, name=exp_name),
            param_space=search_space,)
    results = tuner.fit()
    print("Best config is:", results.get_best_result().config)

if __name__ == "__main__":
    main()
