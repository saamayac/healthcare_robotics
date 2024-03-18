from model.GeoModel import GeoModel
import time
from os.path import join

# please do: pip install mesa mesa-geo
if __name__ == "__main__":
    results_folder='nov21_2'
    model = GeoModel(n_doctors=2, n_nurses=2, ocupation=70, n_shifts=3)
    print('model initialized')

    print('model started running')
    start_time=time.time()
    model.run_model()
    end_time=time.time()
    print("--- running for %s seconds ---" % (end_time - start_time))
    print(model.counts)

    # save information dataframes
    model.datacollector.get_agent_vars_dataframe().to_csv(join('data', results_folder,'agents.csv'))
    model.datacollector.get_model_vars_dataframe().to_csv(join('data',results_folder,'model.csv'))
    model.setup_df['steps (minutes)']=model.schedule.steps
    model.setup_df['computation_time']='{:0.2f}'.format(end_time-start_time)
    model.setup_df.to_csv(join('data',results_folder,'info.csv'))