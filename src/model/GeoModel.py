import mesa
import mesa_geo as mg

from agents.PersonAgent import NurseAgent, DoctorAgent, PatientAgent
from agents.SpaceAgent import SpaceAgent
from agents.HospitalAgent import HospitalAgent
from model.Schedulers import HospitalScheduler

from os.path import join
import geopandas as gpd 
import pandas as pd
import random

class GeoModel(mesa.Model): 
 
    def __init__(self, n_doctors=2, n_nurses=3, ocupation=10, n_shifts=3):
        """Create a new GeoModel."""
        self.running = True
        self.number_shifts = n_shifts
        self.schedule = HospitalScheduler(self)
        self.current_id=0
        self.hit_list = []

        # Scheduled actions time
        self.resample_variables()
        self.action_state = {# shift actions
                             'do-informative-meeting': 'in-meeting',
                             'do-inventory': 'taking-inventory',
                             'do-document': 'documenting',

                             # patient-related actions
                             'do-admit': 'admitting',
                             'do-evaluate': 'evaluating', 
                             'do-medicate': 'medicating',

                             # patient actions
                             'request-admission': 'waiting-admission', # interaction with nurse starts 'in-admission' 
                             'request-evaluation': 'waiting-evaluation', # interaction with doctor starts 'in-evaluation' 
                             'request-medication': 'waiting-medication', # interaction with nurse starts 'in-medication'
                             }
        
        # action priority: 1 urgent (stop the rest of the tasks until it is executed), 0 not urgent
        # only tasks without waiting time can be urgent
        self.action_priority = {'remove': 0,
                                'do-informative-meeting': 2,
                                'do-inventory': 2,
                                'do-document': 0,
                                'do-admit': 1,
                                'do-evaluate': 1,
                                'do-medicate': 1,
                                'request-admission': 0,
                                'request-evaluation': 0,
                                'request-medication': 0,
                                }
        
        # counts for performance metrics
        self.collected_fields = ["empty","ocupied",
                                 "doctor", "nurse", "patient", 
                                 "resting","idle_nurse","idle_doctor", "walking",
                                 'in-admission','in-evaluation','in-medication'] + list(self.action_state.values())
        self.reset_counts()

        # create hospital space
        self.space = HospitalAgent()
        self.doctors=[]; self.nurses=[]

        # SpaceAgents: read from files and add to model
        file_path=join ('data','floorplans','unisabana_hospital_%s.geojson')
        file_names=['floor','polygons']
        df_space = pd.concat((gpd.read_file(file_path%file) for file in file_names),ignore_index=True)
        space_agents = mg.AgentCreator(agent_class=SpaceAgent, model=self).from_GeoDataFrame(df_space)  
        self.space.add_SpaceAgents(space_agents)
 
        # PersonAgent Constructors 
        n_patients=int(ocupation*self.space.floor.patient_availability/100)
        self.init_poputation(n_doctors, n_nurses, n_patients)

        # Add the SpaceAgents to schedule AFTER person agents, to allow them to update their ocupation by using BaseScheduler   
        for agent in space_agents: self.schedule.add(agent)

        # initialize data collector
        model_reporters={key : [lambda key: self.counts[key], [key]] for key in self.counts}
        agent_reporters={'atype':'atype', 'position':'geometry', 'state':'state'}
        self.datacollector = mesa.DataCollector(model_reporters, agent_reporters, tables=None)

        # collect initialization of the model
        self.setup_df=pd.DataFrame({'n_doctors':n_doctors, 'n_nurses':n_nurses, 'max_ocupation':ocupation, 
                                    'capacity': self.space.floor.patient_availability,
                                    'n_shifts': n_shifts}, index=['setup'])

    def resample_variables(self):
        # lifetime related
        self.patient_stay_length = random.triangular(12*60, 24*60) #tp
        self.time_between_patients = random.triangular(2*60, 5*60) #tb
        self.shift_length = 7*60 #shift length

        # shift related
        self.walking_speed = 15 # steps per time tick
        self.shift_transfer_meeting_time = random.triangular(30, 40)
        self.inventory_time = random.triangular(30, 40)
        self.documentation_time = random.triangular(5, 10)
        # do medication round every two hours
        self.medicine_round_frequency = 120
        self.next_medication_time = self.schedule.steps-self.schedule.steps%self.medicine_round_frequency+self.medicine_round_frequency

        # patient related
        self.medication_application_time = random.triangular(5, 10)
        self.admission_time = random.triangular(20, 30)
        self.evaluation_time = random.triangular(20, 30)
        self.evaluation_frequency = random.triangular(4*60, 6*60)
        

    def init_poputation(self, n_doctors, n_nurses, n_patients):
        """Add population to model."""
        # AgentCreators
        self.ac_doctors = mg.AgentCreator( DoctorAgent, model=self, crs=self.space.crs)
        self.ac_nurses = mg.AgentCreator( NurseAgent, model=self, crs=self.space.crs)
        self.ac_patients = mg.AgentCreator( PatientAgent, model=self, crs=self.space.crs)
        # add agents
        self.add_PersonAgents(self.ac_doctors, n_doctors, self.space.nurse_station)
        self.add_PersonAgents(self.ac_nurses, n_nurses, self.space.nurse_station)
        for _ in range(n_patients): # add patients at different times
            self.schedule.patient_arrivals.append(self.schedule.steps + int(random.triangular(0, self.shift_length)))
            self.resample_variables()

    def add_PersonAgents(self, agentCreator, amount, this_spaces, do_shift_takeover=False): 
        """Add population to model."""
        if isinstance(this_spaces,SpaceAgent): this_spaces=[this_spaces]*amount 
        for this_space in this_spaces:
            # create person on this_space centroid
            this_person = agentCreator.create_agent(this_space.geometry.centroid, "P%i"%super().next_id())
            self.schedule.add(this_person)
            self.space.add_agents(this_person)
            # return person if shift takeover is needed
            if do_shift_takeover: return this_person

    def reset_counts(self):
        self.counts = dict.fromkeys(self.collected_fields,0)

    def step(self):
        """Run one step of the model."""
        print(f'GeoModel: {100*self.schedule.steps/(self.number_shifts*self.shift_length):.2f}%', end='\r')
        self.reset_counts()
        self.schedule.step()
        while len(self.hit_list) > 0:
            agent = self.hit_list.pop()
            self.schedule.remove(agent)
            self.space.remove_agent(agent)
        self.space._recreate_rtree() # recalculate spatial tree, because agents are moving

        if self.schedule.steps>0: # start collecting data after warm-up time
            self.datacollector.collect(self)

        # stop criteria
        if self.schedule.steps>=self.number_shifts*self.shift_length:
            self.running = False
            print(f'GeoModel: run completed')
            