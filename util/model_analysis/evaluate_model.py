import sys
sys.path.append("/home/nrubio/Desktop/junction_pressure_differentials")
from util.unified0D_plus.apply_unified0D_plus  import *
from util.unified0D_plus.graph_to_junction_dict import *

from util.regression.neural_network.training_util import *
from util.tools.graph_handling import *
from util.tools.basic import *
import tensorflow as tf
import dgl
from dgl.data import DGLDataset

def get_re(flow, radius):
    u = flow/(np.pi * radius**2)
    d = 2*radius
    rho = 1.06
    mu = 0.04
    return rho*u*d/mu

def dP_poiseuille(flow, radius, length):
    mu = 0.04
    dP = 8 * mu * length * flow /(np.pi * radius**4)
    return dP

def vary_param(anatomy, variable, dP_type):
    plt.clf()

    if anatomy == "mynard":
        #model_name = "1_hl_52_lsmlp_0_0931_lr_0_008_lrd_1e-05_wd_bs_29_nepochs_300_seed_0_geos_187_dP"
        model_name = "1_hl_70_lsmlp_0_0931_lr_0_008_lrd_1e-05_wd_bs_29_nepochs_300_seed_0_geos_187"#mynard
        char_val_dict = load_dict(f"data/characteristic_value_dictionaries/mynard_vary_rout_synthetic_data_dict")
        scaling_dict = load_dict(f"data/scaling_dictionaries/mynard_rand_scaling_dict")

    elif anatomy == "Aorta":
        model_name = "1_hl_52_lsmlp_0_0931_lr_0_008_lrd_1e-05_wd_bs_29_nepochs_300_seed_0_geos_110_dP"#aorta
        char_val_dict = load_dict(f"data/characteristic_value_dictionaries/Aorta_vary_rout_synthetic_data_dict")
        scaling_dict = load_dict(f"data/scaling_dictionaries/Aorta_rand_scaling_dict")

    elif anatomy == "Pulmo":
        model_name = "1_hl_52_lsmlp_0_0931_lr_0_008_lrd_1e-05_wd_bs_29_nepochs_300_seed_0_geos_123_dP"
        char_val_dict = load_dict(f"data/characteristic_value_dictionaries/Pulmo_vary_rout_synthetic_data_dict")
        scaling_dict = load_dict(f"data/scaling_dictionaries/Pulmo_rand_scaling_dict")

    nn_model = tf.keras.models.load_model("results/models/neural_network/steady/"+model_name+"_steady", compile=True)
    #print(nn_model.get_config())
    dPs = []
    for i in reversed(range(int(len(char_val_dict["name"])/2))):

        if i/int(len(char_val_dict["name"])/2) < 0.5:
            outlet_ind = 1
        else:
            outlet_ind = 0
        print(outlet_ind)

        #print(char_val_dict)
        inlet_data = np.stack((scale(scaling_dict, char_val_dict["inlet_area"][2*i], "inlet_area").reshape(1,-1),
                                scale(scaling_dict, char_val_dict["inlet_length"][2*i], "inlet_length").reshape(1,-1),
                                )).T

        outlet_data = np.stack((
            scale(scaling_dict, np.asarray(char_val_dict["outlet_area"][2*i: 2*(i+1)]), "outlet_area"),
            scale(scaling_dict, np.asarray(char_val_dict["outlet_length"][2*i: 2*(i+1)]), "outlet_length"),
            scale(scaling_dict, np.asarray(char_val_dict["angle"][2*i: 2*(i+1)]), "angle"),
            )).T
        #print(outlet_data)
        outlet_flows = np.stack((np.asarray(char_val_dict["flow_list"][2*i]).T,
                                np.asarray(char_val_dict["flow_list"][2*i + 1]).T))

        outlet_dPs = np.stack((np.asarray(char_val_dict["dP_list"][2*i]).T,
                                np.asarray(char_val_dict["dP_list"][2*i + 1]).T))

        outlet_junction_dPs = np.stack((np.asarray(char_val_dict["dP_junc_list"][2*i]).T,
                                np.asarray(char_val_dict["dP_junc_list"][2*i + 1]).T))

        outlet_coefs = np.asarray([scale(scaling_dict, char_val_dict["coef_a"][2*i: 2*(i+1)], "coef_a"),
                                scale(scaling_dict, char_val_dict["coef_b"][2*i: 2*(i+1)], "coef_b")]).T

        geo_name = "".join([let for let in char_val_dict["name"][2*i] if let.isnumeric()])
        geo_name = int(geo_name)

        inlet_outlet_pairs = get_inlet_outlet_pairs(1, 2)
        outlet_pairs = get_outlet_pairs(2)
        graph = dgl.heterograph({('inlet', 'inlet_to_outlet', 'outlet'): inlet_outlet_pairs,('outlet', 'outlet_to_outlet', 'outlet'): outlet_pairs})
        graph  = graph.to("/cpu:0")

        with tf.device("/cpu:0"):

            graph.nodes["inlet"].data["inlet_features"] = tf.reshape(tf.convert_to_tensor(inlet_data, dtype=tf.float64), [1,-1])
            graph.nodes["outlet"].data["outlet_features"] = tf.convert_to_tensor(outlet_data, dtype=tf.float64)
            graph.nodes["outlet"].data["outlet_flows"] = tf.convert_to_tensor(outlet_flows, dtype=tf.float64)
            if dP_type == "end":
                graph.nodes["outlet"].data["outlet_dP"] = tf.convert_to_tensor(outlet_dPs, dtype=tf.float64)
            elif dP_type == "junction":
                graph.nodes["outlet"].data["outlet_dP"] = tf.convert_to_tensor(outlet_junction_dPs, dtype=tf.float64)
            graph.nodes["inlet"].data["geo_name"] = tf.constant([geo_name])
            graph.nodes["outlet"].data["outlet_coefs"] = tf.convert_to_tensor(outlet_coefs, dtype=tf.float64)
        #print(graph.nodes["outlet"].data)

        master_tensor = get_master_tensors_steady([graph])
        input_tensor = master_tensor[0]; print(input_tensor)
        flow_tensor = master_tensor[2]
        dP = master_tensor[4]

        flow_tensor_cont = tf.linspace(flow_tensor[outlet_ind,0], flow_tensor[outlet_ind,-1], 100)
        inflow_tensor_cont =  tf.linspace(flow_tensor[0,0], flow_tensor[0,-1], 100) \
                            + tf.linspace(flow_tensor[1,0], flow_tensor[1,-1], 100)

        pred_outlet_coefs = tf.cast(nn_model.predict(input_tensor), dtype=tf.float64)
        #print(pred_outlet_coefs); pdb.set_trace()
        pred_dP = tf.reshape(inv_scale_tf(scaling_dict, pred_outlet_coefs[outlet_ind,0], "coef_a"), (-1,1)) * tf.square(flow_tensor_cont) + \
                    tf.reshape(inv_scale_tf(scaling_dict, pred_outlet_coefs[outlet_ind,1], "coef_b"), (-1,1)) * flow_tensor_cont

        dPs.append(np.asarray(pred_dP))

        junction_dict_global = graphs_to_junction_dict_steady_cont([graph], scaling_dict)

        flow_arr = flow_tensor.numpy()
        dP_mynard_list = []
        print(char_val_dict["outlet_radius"])
        if dP_type == "end":
            for j in range(1,100):
                    dP_mynard_list = dP_mynard_list + [apply_unified0D_plus(junction_dict_global[j])[outlet_ind] \
                                    + 0.00035*get_re(flow = flow_tensor_cont[j], radius = char_val_dict["outlet_radius"][2*i+outlet_ind])
                                    - dP_poiseuille(flow = inflow_tensor_cont[j], radius = char_val_dict["inlet_radius"][2*i], length = char_val_dict["inlet_length"][2*i]) \
                                    - dP_poiseuille(flow = flow_tensor_cont[j], radius = char_val_dict["outlet_radius"][2*i+outlet_ind], length = char_val_dict["outlet_length"][2*i+outlet_ind])]
        elif dP_type == "junction":
            for j in range(1,100):
                    dP_mynard_list = dP_mynard_list + [apply_unified0D_plus(junction_dict_global[j])[outlet_ind]]
        dP_mynard = np.asarray(dP_mynard_list)

        if variable == "rout":
            plt.plot(np.asarray(flow_tensor_cont), np.asarray(tf.reshape(pred_dP, [-1,]))/1333, label = "$r_{outlet}$" + f" = { char_val_dict['outlet_radius'][2*i+outlet_ind]:.2f} cm", c = colors[i+1], linewidth=2)

            plt.plot(np.asarray(flow_tensor_cont)[1:], dP_mynard/1333, "--", c = colors[i+1], linewidth=2 )
            #plt.plot(np.asarray(flow_tensor_cont)[1:], dP_mynard/1333, "--", c = colors[i], linewidth=2, label = f"unified0D_plus")

        if variable == "angle":
            plt.plot(np.asarray(flow_tensor_cont), np.asarray(tf.reshape(pred_dP, [-1,]))/1333, label = f"Outlet Angle = {char_val_dict['angle'][2*i+1]:.2f} $^\circ$", c = colors[i])

        # U_in = np.asarray(flow_tensor[0,1:] + flow_tensor[1,1:])
        # U_out = np.asarray(flow_tensor)[outlet_ind,1:]
        # K = -(np.asarray(dP)[outlet_ind,1:] - (0.5*1.06*(U_in**2 - U_out**2)))/ (0.5* 1.06 * U_in**2)

        plt.scatter(np.asarray(flow_tensor)[outlet_ind,:], np.asarray(dP)[outlet_ind,:]/1333, c = colors[i+1], marker = "*", s = 100)
        #plt.scatter(np.asarray(flow_tensor)[outlet_ind,1:], K, c = colors[i], marker = "*", s = 100)

    plt.xlabel("$Q \;  (\mathrm{cm^3/s})$")
    plt.ylabel("$\Delta P$ (mmHg)")
    plt.legend(fontsize="14", loc = "upper center", bbox_to_anchor = (0.5, 1.33))
    fig = plt.gcf()
    fig.set_size_inches(3,4)
    fig.savefig(f"results/model_visualization/{anatomy}_{variable}_vs_predicted_dps_{dP_type}_steady.pdf", bbox_inches='tight', format = "pdf")
    return

anatomy = sys.argv[1];
vary_param(anatomy, "rout", "end")
