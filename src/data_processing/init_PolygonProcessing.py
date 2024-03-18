# import/install necessary libraries
try:
    import pandas as pd
    import json
    from PIL import Image
    import numpy as np
    import rasterio.features
except:
    import os
    cmds=['pip install --upgrade pip', 'pip install pandas json PIL rasterio numpy']
    for cmd in cmds: os.system(cmd)

# transform hospital layout into geo-referenced polygon
def generate_non_axis_aligned_rectangular_mesh(polygon,X,shape):
    # define grid shape and steps
    x_A, y_A, x_B, y_B, x_D, y_D = polygon
    min_x, min_y, max_x, max_y = shape
    num_rows = (max_y-min_y); num_cols=(max_x-min_x)
    x_step = (x_B - x_A) / num_cols; y_step = (y_D - y_A) / num_rows

    # transform and store each shape point
    mesh_points = []
    for x, y in X:
        x_ = x_A + (x-min_x) * x_step  + (y-min_y) * (x_D - x_A) / num_rows
        y_ = y_A + (y-min_y) * y_step  + (x-min_x) * (y_B - y_A) / num_cols
        mesh_points.append([x_, y_])
    return mesh_points

# load polygon information into geojson format
def process_type(attributes,shape):
    # save a list of each shape's edges [pixels]
    if shape=='rect':
        x=int(attributes['x']); y=int(attributes['y'])
        dx=int(attributes['width']); dy=int(attributes['height'])
        return [[x,y],[x+dx,y],[x+dx,y+dy],[x,y+dy]]
    else:
        x=attributes['all_points_x']; y=attributes['all_points_y']
        return [[int(x),int(y)] for x,y in zip(x,y)]
    

def csv_to_geojson(data):
    # load dictionary columns of information
    dict_cols=['region_shape_attributes','region_attributes']
    data[dict_cols]=data[dict_cols].map(lambda x: json.loads(x))

    # process 'rect' and 'polygon' shapes
    data['type']=data['region_shape_attributes'].apply(lambda x: x['name'])
    for shape,df_shape in data.groupby('type', group_keys=False)['region_shape_attributes']:
        data.loc[df_shape.index,'pixls_coor']=df_shape.apply(process_type,args=[shape])
 
    # get shape size (pixels)
    maxpxl_x,maxpxl_y=pd.DataFrame(data['pixls_coor'].apply(max).values.tolist()).max()
    minpxl_x,minpxl_y=pd.DataFrame(data['pixls_coor'].apply(min).values.tolist()).min()

    # transform original map into hospital polygon coordinates (lat,lon)
    

    x_D,y_D=-74.03022175880785, 4.85676327975284
    x_A,y_A=-74.03131594596519, 4.856075646396405
    x_B,y_B=-74.03094817465468, 4.855513318496804

    x_D,y_D=-74.03032717497169, 4.856395769426385
    x_A,y_A=-74.03051378129385, 4.85627127054282
    x_B,y_B=-74.03041061260339, 4.856126318231986
    

    polygon=[x_A, y_A, x_B, y_B, x_D, y_D]
    shape=[minpxl_x,minpxl_y,maxpxl_x,maxpxl_y]
    mesh=lambda X: generate_non_axis_aligned_rectangular_mesh(polygon,X,shape)
    data[['coordinates']]=data[['pixls_coor']].map(lambda x: mesh(x))
    data[['coordinates']]=data[['coordinates']].map(lambda x: x+[x[0]])

    # save with geojson format
    features=[]
    for i,feature in data.iterrows():
        att_name= lambda k: 'number' if k=='Id' else 'atype' if k=='name' else k
        info={"type": "Feature",
                "properties": {att_name(k):x.strip() for k,x in feature['region_attributes'].items()},
                "geometry":{"coordinates":[feature['coordinates']], "type": "Polygon"},
                "id":i}
        features.append(info)

    # download file (visualize on https://geojson.io/#new&map=2/0/20)
    geojson={"type": "FeatureCollection", "features": features}
    with open('data/floorplans/unisabana_hospital_polygons.geojson', 'w') as convert_file:
        geojson_file=json.dumps(geojson)
        convert_file.write(geojson_file)
    return geojson_file, polygon, shape


def img_to_geojson(img,polygon,shape):
    # mask image (walls are black)
    bw = np.array(img.point(lambda x: 0 if x<220 else 255, '1'))
    # turn image into polygons
    maskShape = rasterio.features.shapes(bw.astype('uint8'))
    mypoly=[vec[0] for vec in maskShape]

    # save with geojson format
    mesh=lambda X: generate_non_axis_aligned_rectangular_mesh(polygon,X,shape)
    features=[]
    for i,geometry in enumerate(mypoly[1:-1]):
        mypoly[i]['coordinates']=[mesh(geometry['coordinates'][0])]
        info={"type": "Feature",
                "properties":{"atype":"floor","number":"2"},
                "geometry":mypoly[i],
                "id":i}
        features.append(info)
    # download file (visualize on https://geojson.io/#new&map=2/0/20)
    geojson={"type": "FeatureCollection", "features": features}
    with open('data/floorplans/unisabana_hospital_floor.geojson', 'w') as convert_file:
        geojson_file=json.dumps(geojson)
        convert_file.write(geojson_file)
    return geojson_file


if __name__ == "__main__":
    # load shape annotations (create/edit on https://www.robots.ox.ac.uk/~vgg/software/via/via_demo.html)
    data=pd.read_csv('data/floorplans/polygons/unisabana_hospital_csv.csv')
    # save with geojson format
    geojson_file,geo_polygon,geo_shape=csv_to_geojson(data)

    # load floor limits
    img = Image.open('data/floorplans/pngs/floorII_walls.png').convert("L")
    # save with geojson format
    geojson_file=img_to_geojson(img,geo_polygon,geo_shape)