from mesa.time import BaseScheduler
from mesa.model import Model
import heapq

class HospitalScheduler(BaseScheduler):
    def __init__(self, model: Model) -> None: 
        super().__init__(model)
        self.patient_arrivals=[]

    def step(self) -> None:
        """Execute the step of all the agents, one at a time."""
        # To be able to remove and/or add agents during stepping
        # it's necessary for the keys view to be a list.
        super().step()

        # Add new patients
        n_new_patients = self.patient_arrivals.count(self.steps)
        if n_new_patients > 0:
            self.model.add_PersonAgents(self.model.ac_patients, n_new_patients, self.model.space.get_empty_beds(n_new_patients))


class PersonScheduler:
    def __init__(self, owner):
        self.owner = owner
        self.dummy_counter = 0
        self.task_queue = []  # Priority queue to manage tasks
        self.hold_next_action = 0  # Time to wait before executing next task
        self.hold_current_action = False # Time to wait before executing current task
        self.do_finish_task = False  # flag to finish current task
        
    def add_scheduled_task(self, freq=0, execute_in=0, **task_kwargs):
        action_priority = -self.owner.model.action_priority[task_kwargs['action']]
        start_time = self.owner.model.schedule.steps + execute_in # Calculate the first scheduled time
        heapq.heappush(self.task_queue, (action_priority, start_time, self.dummy_counter, freq, task_kwargs))  # Add the task with its frequency
        self.dummy_counter += 1

    def execute_schedule(self, current_time):
        """Execute next task if it's time to do so and there is no previous task in progress."""
        if self.do_finish_task: 
            # trigger functions at the end of the task
            self.owner.terminate_task()
            self.do_finish_task = False

        if self.hold_next_action > 0 or self.hold_current_action: # if there is a task in progress
            self.owner.execute_task()
            return None
        
        try: # if there is a task in the queue
            _, next_time, _, freq, task_kwargs = self.task_queue[0]
        except IndexError:
            return None

        if current_time >= next_time:
            self.owner.prepare_task(**task_kwargs)
            if not self.hold_current_action: # if task can start immediately
                heapq.heappop(self.task_queue)
                if freq > 0:
                    self.add_scheduled_task(freq=freq, execute_in=freq + next_time - current_time, **task_kwargs)
            self.owner.execute_task() # execute task