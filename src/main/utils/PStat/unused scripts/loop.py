import experiment

class loop(experiment):
    def __init__(self):
        self.experiment_list = []
        self.exit_loop = False
    def add_experiment(self, experiment):
        self.experiment_list.append(experiment)
    def check_experiments(self):
        for experiment in self.experiment_list:
            experiment.check()
        print("All the experiments have been checked")
    
