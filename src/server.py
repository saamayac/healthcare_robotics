import mesa
import mesa_geo as mg
from model.GeoModel import GeoModel
from agents.PersonAgent import PersonAgent


############## define server ##############
class Text(mesa.visualization.TextElement):
    """Display a text"""
    def __init__(self): pass
    def render(self, model): return "Hospital Time (minutes): " + str(model.schedule.steps)

model_params = {"ocupation": mesa.visualization.Slider("Bed's ocupation %", 10, 0, 100, 10),
                "n_nurses": mesa.visualization.Slider("Nurses", 5, 1, 10, 1),
                "n_doctors": mesa.visualization.Slider("Doctors", 2, 1, 10, 1),
                "n_shifts": mesa.visualization.Slider("Simulation Shifts", 3, 1, 10, 1),
                }

def agent_draw (agent):
    """ Portrayal Method for canvas """
    portrayal = {}  
    if isinstance(agent, PersonAgent): 
        # color by type
        if agent.atype in ["patient"]: color='Blue'  
        elif agent.atype in ["doctor"]: color='Black'
        elif agent.atype in ["nurse"]: color='Green'
        
        portrayal["radius"] = "1"
        portrayal["color"] = color

    elif agent.atype=='bed':
        if agent.state=='ocupied': 
            portrayal["color"] = "Red"
            portrayal["fillOpacity"] = 0.1
        else: 
            portrayal["color"] = "Green"
            portrayal["fillOpacity"] = 0.1

    elif agent.atype in ['cart','nurse_station','medication_station']:
        portrayal["color"] = "Brown" 
        portrayal["fillOpacity"] = 0.05 
    
    elif agent.atype=='room':
        portrayal["color"] = "White" 
        portrayal["fillOpacity"] = 0.05

    else : 
        portrayal["color"] = "Black" 
        portrayal["fill"] = False
    
    return portrayal

map_element = mg.visualization.MapModule(agent_draw, map_height=800, map_width=800, tiles=None)

agents_chart = mesa.visualization.ChartModule(
    [   {"Label": "doctor", "Color": "Black"},
        {"Label": "patient", "Color": "Blue"},
        {"Label": "nurse", "Color": "Green"},
    ])

server = mesa.visualization.ModularServer(
    GeoModel,
    [map_element, Text(), agents_chart],
    "Hospital de la Sabana - ABMS",
    model_params,       
)

############## run server: launchs on browser ##############
if __name__ == "__main__":
    server.launch()       