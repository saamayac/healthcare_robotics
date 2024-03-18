import numpy as np
from fractions import Fraction

class pixelate_floorplan:
    
    def __init__(self, floor, MAX_DENOM = 5, zoom_factor = 1):
        self.MAX_DENOM = MAX_DENOM
        self.zoom_factor = zoom_factor

        # get geolocated floor boundary
        nodes=np.array(floor.geometry.boundary.coords.xy).T

        # store pixelation constants
        self.min_geo_val=nodes.min(axis=0)
        self.factors=np.apply_along_axis(self.legal_intergerize,0,nodes*self.zoom_factor)

        # get pixelate floor boundary
        self.pxl_nodes=self.pixelate(nodes)

        # get vertices connecting pixelated nodes with Bresenham's line algorithm (no diagonals allowed)
        pxl_vertices = []
        for (x0,y0), (x1,y1) in zip(self.pxl_nodes[:-1,:],self.pxl_nodes[1:,:]):
            pxl_vertices.extend(self.bresenham_noDiag(x0, y0, x1, y1))
            
        self.ox, self.oy = list(zip(*pxl_vertices))
        self.ox, self.oy = list(self.ox), list(self.oy)

        # store depixelation constants
        self.depixel_constant=np.ptp(self.pxl_nodes,axis=0)/np.ptp(nodes,axis=0)
        self.min_pxl_val=self.pxl_nodes.min(axis=0)

    def pixelate(self, geo_points_list):
        pxlted= np.apply_along_axis(lambda x: np.round(x*self.factors*self.zoom_factor),1,geo_points_list).astype(int)
        return pxlted.astype(int)

    def depixelate(self, pxl_path):
        new_line=((pxl_path-self.min_pxl_val)/self.depixel_constant)+self.min_geo_val
        return new_line

    def legal_intergerize(self,pxl_boundary):
        fractions = [Fraction(val).limit_denominator(self.MAX_DENOM) for val in pxl_boundary]
        ratios = np.array([(f.numerator, f.denominator) for f in fractions])
        factor = np.lcm.reduce(ratios[:,1])
        return factor
    
    """Implementation of Bresenham's line drawing algorithm
    See en.wikipedia.org/wiki/Bresenham's_line_algorithm
    """
    def bresenham_noDiag(self, x0, y0, x1, y1):
        """Yield integer coordinates on the line from (x0, y0) to (x1, y1).
        Input coordinates should be integers.
        this implementation does not allow diagonal movement
        """
        dx = abs(x1 - x0); dy = -abs(y1 - y0)
        xstep = 1 if x1 > x0 else -1; ystep = 1 if y1 > y0 else -1
        manhatan_dist = dx + dy

        while (x1 != x0) or (y1 != y0):
            yield x0, y0
            if (2*manhatan_dist-dy) > (dx-2*manhatan_dist):
                # horizontal step
                manhatan_dist+=dy
                x0+=xstep
            else: # vertical step
                manhatan_dist+=dx
                y0 += ystep

        yield x0, y0       


def check_path(path, floor):
    colision_points = floor.geometry.boundary.intersection(path)
    return colision_points.is_empty, colision_points