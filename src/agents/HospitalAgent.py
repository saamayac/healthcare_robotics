import mesa_geo as mg
import pickle
from typing import Set
from agents.SpaceAgent import SpaceAgent
from data_processing.FloorNavigation import DStarLite

class HospitalAgent(mg.GeoSpace):
    rooms: Set[SpaceAgent]
    beds: Set[SpaceAgent]
    nurse_station: SpaceAgent
    medication_station: SpaceAgent
    floor: SpaceAgent

    def __init__(self) -> None:
        super().__init__(warn_crs_conversion=False)
        self.rooms = set()
        self.beds = set()
        self.nurse_station = None
        self.medication_station = None
        self.floor = None
        self.dstarlite = None
        self.cache_paths = {}
        self.comparison_buffer=0.2

    def add_SpaceAgents(self, agents) -> None:
        super().add_agents(agents)
        for agent in agents:
            if agent.atype == 'room': self.rooms.add(agent)
            if agent.atype == 'bed': 
                self.beds.add(agent)
                agent.patient_availability = 1 # fix bed's patient capacity to 1
            elif agent.atype == 'nurse_station': self.nurse_station = agent
            elif agent.atype == 'medication_station': self.medication_station = agent
            elif agent.atype == 'floor':
                self.floor = agent
                self.init_floor_navigation()
        self.set_containing_relations(self.beds,'room')
        self.set_containing_relations(self.rooms,'floor')

    def init_floor_navigation(self):
        # prepare path creation object and load previous paths
        self.dstarlite = DStarLite(self.floor, zoom_factor=0.09)
        try: 
            with open("data/paths/cache_paths.pkl", "rb") as cache_file:
                self.cache_paths = pickle.load(cache_file)
        except:
            self.cache_paths = {}

    def get_path (self, from_agent, to_agent):
        
        # start and finish geo-points
        start=from_agent.geometry.centroid; end=to_agent.geometry.centroid

        # try to find path in cache
        for (path_start, path_end), path in self.cache_paths.items():
            if start.within(path_start.buffer(self.comparison_buffer)) and end.within(path_end.buffer(self.comparison_buffer)): return path.tolist()

        # if not on cache: calculate shortest path
        found_path, stepByStep_Path = self.dstarlite.main(start, end)
        if not found_path: raise NameError ('path not found from %s to %s'%(str(start),str(end)))
        
        # update cache of paths
        self.cache_paths[(start,end)] = stepByStep_Path
        self.cache_paths[(end,start)] = stepByStep_Path[::-1]
        with open("data/paths/cache_paths.pkl", "wb") as cache_file: pickle.dump(self.cache_paths,cache_file)

        return stepByStep_Path.tolist()

    def set_containing_relations(self, inner, outer_type) -> None:
        """Relate rooms to beds."""
        for small_space in inner:
            outer_area=self.get_relation_to_Agent(small_space, 'within', outer_type, to_centroid=True)
            for space in outer_area:
                space.inner_areas.add(small_space)
                space.patient_availability += small_space.patient_availability
                small_space.area=space

    def get_empty_beds(self, amount) -> Set[SpaceAgent]:
        """Return an empty bed on the rooms with the least number of ocupied beds."""
        if amount > len(self.beds): raise NameError('NotEnoughBeds')
        selected_beds=0
        while selected_beds < amount:
            sorted_rooms = sorted(self.rooms, key=lambda room: room.patient_availability, reverse=True)
            for room in sorted_rooms:
                #this_empty_bed=next((bed for bed in room.beds if bed.patient_ocupation==0), None)
                for this_empty_bed in filter(lambda bed: bed.patient_ocupation==0, room.inner_areas):
                    this_empty_bed.set_ocupied()
                    selected_beds+=1
                    yield this_empty_bed
                    if selected_beds >= amount: return

    def get_relation_to_Agent(self, agent, relation, agent_type, to_centroid=False):
        """Return a list of related agents.

        Parameters:
            agent: the agent for which to compute the relation
            relation: must be one of 'intersects', 'within', 'contains', 'touches'
            agent_type: the type of agent to look for
        """
        possible_agents = self._agent_layer._get_rtree_intersections(agent.geometry)
        reference_geometry = agent.geometry.centroid if to_centroid else agent.geometry
        for other_agent in possible_agents:
            if (
                getattr(reference_geometry, relation)(other_agent.geometry)
                and other_agent.unique_id != agent.unique_id
                and other_agent.atype == agent_type
            ):
                yield other_agent # this is a generator of all matches
        return None # if no matches, return None