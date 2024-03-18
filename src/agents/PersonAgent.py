import mesa_geo as mg
from shapely.geometry import Point
from model.Schedulers import PersonScheduler

class PersonAgent(mg.GeoAgent):

    def __init__(self, unique_id, model, geometry, crs, agent_type):
        """Create a new Person agent."""
        super().__init__(unique_id, model, geometry, crs)
        self.atype = agent_type

        self.scheduler=PersonScheduler(self)
        self.set_idle()
        self.interacting_with = None
        
        self.own_medication_frequency = self.model.medicine_round_frequency
        self.own_medication_application_time = self.model.medication_application_time
        self.life_time=0
        self.initialize()
        self.count_agents()

    def set_idle(self):
        pass
    
    def count_agents(self):
        """Count agents in the model."""
        self.model.counts[self.state] += 1
        self.model.counts[self.atype] += 1

    def initialize(self):
        """Set time to stop being active and schedule initial actions."""
        pass

    def step(self):
        """Advance one step"""
        self.scheduler.execute_schedule(self.model.schedule.steps)
        self.model.resample_variables()
        self.count_agents()
        # decrease life time
        self.life_time -= 1
        if self.life_time == 0: self.remove()

    def prepare_task(self, **kwargs):
        '''either hold the current task while walking or hold the next task while executing current'''
        route = kwargs['route'] if 'route' in kwargs else []
        if not route or self.compare_placement(route[-1]):
            action=kwargs['action']
            self.state=self.model.action_state[action]
            self.scheduler.hold_next_action = kwargs['duration'] if 'duration' in kwargs else 1

            # trigger functions at the beginning of the task
            if action=='request-admission': 
                self.register_patient()
                self.nurse.scheduler.add_scheduled_task(action='do-admit',route=[self], 
                                                        duration=self.model.admission_time)
            elif action=='request-evaluation':
                self.doctor.scheduler.add_scheduled_task(action='do-evaluate',route=[self], 
                                                         duration=self.model.evaluation_time)
                self.doctor.scheduler.add_scheduled_task(action='do-document',
                                                         route=[self.model.space.nurse_station], 
                                                         duration=self.model.documentation_time)
            elif action=='request-medication':
                self.nurse.scheduler.add_scheduled_task(action='do-medicate', route=[self.model.space.medication_station, self], 
                                                        duration=self.own_medication_application_time)
                self.nurse.scheduler.add_scheduled_task(action='do-document',
                                                         route=[self.model.space.nurse_station], 
                                                         duration=self.model.documentation_time)
            elif action in ['do-admit','do-evaluate', 'do-medicate']: 
                self.do_interactions(with_=route[-1], mode="initiate")
        
        else:
            self.link_paths(route)
            self.state='walking'
            self.scheduler.hold_current_action = True # hold current task while walking
        
    def compare_placement(self, other_agent) -> bool:
        """Return True if the agent is within radious of the other_agent"""
        return self.geometry.centroid.within(other_agent.geometry.centroid.buffer(self.model.space.comparison_buffer))
    
    def link_paths(self, agents_to_visit):
        """Link paths to multiple agents"""
        start=self; end=agents_to_visit[0]
        self.path = self.model.space.get_path(start, end)
        for location in agents_to_visit[1:]:
            self.path += self.model.space.get_path(end, location)
            end=location
    
    def do_interactions(self, with_=None, mode=None):
        if mode=="initiate" and isinstance(with_, PersonAgent):
            self.interacting_with=with_
            with_.interacting_with=self
            if self.state=='admitting': with_.state='in-admission'
            if self.state=='evaluating': with_.state='in-evaluation'
            if self.state=='medicating': with_.state='in-medication'
        
        elif mode=="terminate" and isinstance(self.interacting_with, PersonAgent):
            if self.state in ['admitting','evaluating','medicating']: 
                self.interacting_with.set_idle()
                self.interacting_with.scheduler.hold_next_action = 0
            self.interacting_with.interacting_with=None
            self.interacting_with=None

    def execute_task(self):
        if self.state=='walking':
            for _ in range(self.model.walking_speed):
                self.geometry = Point(self.path.pop(0))
                if len(self.path)==0: 
                    self.scheduler.do_finish_task = True
                    break

        elif 'waiting' in self.state or self.state in ['in-admission', 'in-evaluation', 'in-medication']:
            self.scheduler.hold_next_action = 1

        else:
            self.scheduler.hold_next_action -= 1
            if self.scheduler.hold_next_action <= 0: self.scheduler.do_finish_task=True
        
    def terminate_task(self):
        if self.state=='walking':
            self.scheduler.hold_current_action=False
            self.set_idle()

        else:
            self.do_interactions(mode="terminate")
            self.set_idle()
        
    def remove(self):
        """Remove agent from model and space."""
        self.model.hit_list.append(self)        
                
class HealthcareAgent(PersonAgent):

    def __init__(self, unique_id, model, geometry, crs, agent_type):
        """Create a new Person agent."""
        super().__init__(unique_id, model, geometry, crs, agent_type)

    def start_shift(self):
        self.life_time=self.model.shift_length
        self.patients=[]
        self.scheduler.add_scheduled_task(action='do-informative-meeting',
                                          route=[self.model.space.nurse_station], 
                                          duration=self.model.shift_transfer_meeting_time)

    def transfer_workload(self, agentCreator):
        new_worker = self.model.add_PersonAgents(agentCreator, 1, self.model.space.nurse_station, do_shift_takeover=True)
        new_worker.scheduler.task_queue.extend(self.scheduler.task_queue)
        new_worker.patients.extend(self.patients)
        for patient in self.patients:
            if patient.nurse==self: patient.nurse=new_worker
            elif patient.doctor==self: patient.doctor=new_worker
                
class NurseAgent(HealthcareAgent):

    def __init__(self, unique_id, model, geometry, crs):
        """Create a new Person agent."""
        super().__init__(unique_id, model, geometry, crs, 'nurse')
    
    def __repr__(self):
        return "NurseAgent_"+str(self.unique_id)

    def set_idle(self):
        self.state='idle_nurse'
        self.path=[]

    def initialize(self):
        """Set time to stop being active and schedule initial actions."""
        self.model.nurses.append(self)
        self.start_shift()
        self.scheduler.add_scheduled_task(action='do-inventory',
                                      route=[self.model.space.medication_station], 
                                      duration=self.model.inventory_time)
        self.scheduler.add_scheduled_task(action='do-document',
                                          route=[self.model.space.nurse_station], 
                                          duration=self.model.documentation_time)
        
    def remove(self):
        """Remove agent from model and space."""
        # if patient, remove and trigger next patient's arrival
        self.transfer_workload(self.model.ac_nurses)
        self.model.nurses.remove(self)
        super().remove()

                
class DoctorAgent(HealthcareAgent):

    def __init__(self, unique_id, model, geometry, crs):
        """Create a new Person agent."""
        super().__init__(unique_id, model, geometry, crs, 'doctor')

    
    def __repr__(self):
        return "DoctorAgent_"+str(self.unique_id)

    def set_idle(self):
        self.state='idle_doctor'
        self.path=[]

    def initialize(self):
        """Set time to stop being active and schedule initial actions."""
        self.model.doctors.append(self)
        self.start_shift()
        
    def remove(self):
        """Remove agent from model and space."""
        self.transfer_workload(self.model.ac_doctors)
        self.model.doctors.remove(self)
        super().remove()
        
class PatientAgent(PersonAgent):

    def __init__(self, unique_id, model, geometry, crs):
        """Create a new Person agent."""
        super().__init__(unique_id, model, geometry, crs, 'patient')
    
    def __repr__(self):
        return "PatientAgent_"+str(self.unique_id)

    def set_idle(self):
        self.state='resting'
        self.path=[]

    def initialize(self):
        """Set time to stop being active and schedule initial actions."""
        self.nurse=None; self.doctor=None
        self.life_time=self.model.patient_stay_length
        self.scheduler.add_scheduled_task(action='request-admission')
        self.scheduler.add_scheduled_task(action='request-evaluation', 
                                          freq=self.model.evaluation_frequency)
        self.scheduler.add_scheduled_task(action='request-medication',
                                          execute_in=self.model.next_medication_time,
                                          freq=self.own_medication_frequency)

    def register_patient(self):
        # assign to doctor & nurse with least patients
        doctor=sorted(self.model.doctors, key=lambda doc: len(doc.patients))[0]
        nurse=sorted(self.model.nurses, key=lambda nurse: len(nurse.patients))[0]
        nurse.patients.append(self); doctor.patients.append(self)
        self.doctor=doctor; self.nurse=nurse
        
    def remove(self):
        """Remove agent from model and space."""
        self.doctor.patients.remove(self); self.nurse.patients.remove(self)
        self.model.schedule.patient_arrivals.append(self.model.schedule.steps + int(self.model.time_between_patients))
        super().remove()
