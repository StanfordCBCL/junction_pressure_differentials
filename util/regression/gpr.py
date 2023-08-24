import sys
sys.path.append("/home/nrubio/Desktop/junction_pressure_differentials")
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import DotProduct, WhiteKernel
from sklearn.gaussian_process.kernels import RBF
from util.regression.neural_network.training_util import *

def train_gpr_model_steady(anatomy, num_geos, seed = 0):

    scaling_dict = load_dict(f"data/scaling_dictionaries/{anatomy}_scaling_dict_steady")
    train_dataset = load_dict(f"data/dgl_datasets/{anatomy}/train_{anatomy}_num_geos_{num_geos}_seed_{seed}_dataset")
    val_dataset = load_dict(f"data/dgl_datasets/{anatomy}/val_{anatomy}_num_geos_{num_geos}_seed_{seed}_dataset")

    train_dataloader = get_graph_data_loader(train_dataset, batch_size = len(train_dataset))
    train_input, train_output, train_flow, train_dP = get_master_tensors_steady(train_dataloader)

    val_dataloader = get_graph_data_loader(val_dataset, batch_size = len(train_dataset))
    val_input, val_output, val_flow, val_dP = get_master_tensors_steady(val_dataloader)

    kernel = RBF(length_scale=1.0, length_scale_bounds=(1e-1, 10.0))
    gpr = GaussianProcessRegressor(kernel=kernel, random_state=0).fit(np.asarray(train_input), np.asarray(train_output))
    pickle.dump(gpr, open(f"results/models/{len(train_dataset)+len(val_dataset)}_gpr", 'wb'))


    pred_coefs_train = tf.convert_to_tensor(gpr.predict(np.asarray(train_input)), dtype =tf.float32)
    pred_dP_train = tf.reshape(inv_scale_tf(scaling_dict, pred_coefs_train[:,0], "coef_a"), (-1,1)) * tf.square(train_flow) + \
                tf.reshape(inv_scale_tf(scaling_dict, pred_coefs_train[:,1], "coef_b"), (-1,1)) * train_flow
    dP_loss_train = mse(pred_dP_train/1333, train_dP/1333)

    pred_coefs_val = tf.convert_to_tensor(gpr.predict(np.asarray(val_input)), dtype =tf.float32)
    pred_dP_val = tf.reshape(inv_scale_tf(scaling_dict, pred_coefs_val[:,0], "coef_a"), (-1,1)) * tf.square(val_flow) + \
                tf.reshape(inv_scale_tf(scaling_dict, pred_coefs_val[:,1], "coef_b"), (-1,1)) * val_flow
    dP_loss_val = mse(pred_dP_val/1333, val_dP/1333)

    return gpr, dP_loss_val, dP_loss_train


def train_gpr_model_unsteady(anatomy, num_geos, seed = 0):

    scaling_dict = load_dict(f"data/scaling_dictionaries/{anatomy}_scaling_dict_steady")
    train_dataset = load_dict(f"data/dgl_datasets/{anatomy}/train_{anatomy}_num_geos_{num_geos}_seed_{seed}_dataset")
    val_dataset = load_dict(f"data/dgl_datasets/{anatomy}/val_{anatomy}_num_geos_{num_geos}_seed_{seed}_dataset")

    train_dataloader = get_graph_data_loader(train_dataset, batch_size = len(train_dataset))
    train_input, train_output, train_flow, train_flow_der, train_dP = get_master_tensors(train_dataloader)

    val_dataloader = get_graph_data_loader(val_dataset, batch_size = len(train_dataset))
    val_input, val_output, val_flow, val_flow_der, val_dP = get_master_tensors(val_dataloader)

    kernel = RBF(length_scale=1.0, length_scale_bounds=(1e-1, 10.0))
    gpr = GaussianProcessRegressor(kernel=kernel, random_state=0).fit(np.asarray(train_input), np.asarray(train_output))
    pickle.dump(gpr, open(f"results/models/{len(train_dataset)+len(val_dataset)}_gpr", 'wb'))

    pred_coefs_train = tf.convert_to_tensor(gpr.predict(np.asarray(train_input)), dtype =tf.float32)
    pred_dP_train = tf.reshape(inv_scale_tf(scaling_dict, pred_coefs_train[:,0], "coef_a"), (-1,1)) * tf.square(train_flow) + \
                tf.reshape(inv_scale_tf(scaling_dict, pred_coefs_train[:,1], "coef_b"), (-1,1)) * train_flow + \
                tf.reshape(inv_scale_tf(scaling_dict, pred_coefs_train[:,2], "coef_L"), (-1,1)) * (train_flow_der)
    dP_loss_train = mse(pred_dP_train/1333, train_dP/1333)

    pred_coefs_val = tf.convert_to_tensor(gpr.predict(np.asarray(val_input)), dtype =tf.float32)
    pred_dP_val = tf.reshape(inv_scale_tf(scaling_dict, pred_coefs_val[:,0], "coef_a"), (-1,1)) * tf.square(val_flow) + \
                tf.reshape(inv_scale_tf(scaling_dict, pred_coefs_val[:,1], "coef_b"), (-1,1)) * val_flow + \
                tf.reshape(inv_scale_tf(scaling_dict, pred_coefs_val[:,2], "coef_L"), (-1,1)) * (val_flow_der)
    dP_loss_val = mse(pred_dP_val/1333, val_dP/1333)

    return gpr, dP_loss_val, dP_loss_train