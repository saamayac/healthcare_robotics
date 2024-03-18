import mesa_geo as mg

class SpaceAgent(mg.GeoAgent):
    def __init__(self, unique_id, model, geometry, crs):
        # file loads agent type (atype) and number (number) attributes
        super().__init__(unique_id, model, geometry, crs)
 
        # patient placement attributes
        self.patient_availability=0
        self.patient_ocupation=0
        self.area=None
        self.inner_areas=set()
    
    @property
    def state(self):
        return 'empty' if self.patient_ocupation==0 else 'ocupied'
        
    def step(self):
        """Advance agent one step."""
        # update ocupation
        patients_here=self.model.space.get_relation_to_Agent(self, 'contains', 'patient', to_centroid=False)
        self.patient_ocupation = len(list(patients_here))
        assert self.patient_ocupation <= self.patient_availability, 'TooManyPatientsHere'
        self.model.counts[self.state] += 1

    def __repr__(self):
        return "SpaceAgent_"+str(self.unique_id)
    
    def set_ocupied(self):
        self.patient_ocupation += 1
        if self.area: self.area.set_ocupied()