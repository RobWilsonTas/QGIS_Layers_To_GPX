import os
from qgis import processing
from qgis.core import (QgsProcessingAlgorithm,QgsProcessingParameterField,QgsProcessingParameterFeatureSource,QgsVectorLayer,QgsProcessingParameterEnum,
    QgsProcessing,QgsProcessingFeedback,QgsProject,QgsProcessingParameterFolderDestination,QgsProcessingParameterExpression, QgsProcessingParameterBoolean)
from datetime import datetime

#Define a class so that it can use QgsProcessingAlgorithm stuff
class LayersToGPX(QgsProcessingAlgorithm):
    
    #These are the lookups for the input variables
    INPUT_POINT = 'INPUT_POINT'
    INPUT_POINT_LABEL = 'INPUT_POINT_LABEL'
    INPUT_POINT_DESCRIPTION = 'INPUT_POINT_DESCRIPTION'
    INPUT_POINT_ALL_FIELDS = 'INPUT_POINT_ALL_FIELDS'
    INPUT_POINT_SYMBOL = 'INPUT_POINT_SYMBOL'
    INPUT_POLY = 'INPUT_POLY'
    INPUT_POLY_FIELD = 'INPUT_POLY_FIELD'
    INPUT_LINE = 'INPUT_LINE'
    INPUT_LINE_FIELD = 'INPUT_LINE_FIELD'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'

    #This part runs first to get the inputs given by the user
    def initAlgorithm(self, config=None):
        
        #Points input
        self.addParameter(QgsProcessingParameterFeatureSource(
                self.INPUT_POINT,'Points layer',types=[QgsProcessing.TypeVectorPoint],optional=True))
        
        #Make an expression for labelling the points
        self.addParameter(QgsProcessingParameterExpression(
            self.INPUT_POINT_LABEL, 'Point label (will be clipped to 20 chars)\nIt might also be wise to put in null handling, e.g "Code" || if("Abundance IS NULL, \'\', "Abundance")', parentLayerParameterName=self.INPUT_POINT, optional=True))
            
        #Make an expression for adding a description to the points
        self.addParameter(QgsProcessingParameterExpression(
            self.INPUT_POINT_DESCRIPTION, 'Point description\nUsing newlines (\\n) can make the description more readable', parentLayerParameterName=self.INPUT_POINT, optional=True))
            
        #Instead of making your own description, you can just dump everything into the cmt field
        self.addParameter(QgsProcessingParameterBoolean(
            self.INPUT_POINT_ALL_FIELDS, 'Put all fields into the gpx description (instead of the above)', defaultValue=False))
        
        #Let the user choose what style of points they want to output
        global pointStyles
        pointStyles = ["Navaid, Amber","City (Small)","Navaid, Black","Navaid, Blue","Navaid, Green","Navaid, Orange","Navaid, Red","Navaid, Violet","Navaid, White","Square, Green","Square, Red","Square, Blue","Triangle, Blue","Triangle, Green","Triangle, Red","Flag, Red"]
        self.addParameter(QgsProcessingParameterEnum(
            self.INPUT_POINT_SYMBOL,'Point style', options=pointStyles,allowMultiple=False, defaultValue='Triangle, Red'))
            
        #Lines input
        self.addParameter(QgsProcessingParameterFeatureSource(
                self.INPUT_LINE,'Lines layer',types=[QgsProcessing.TypeVectorLine],optional=True))
        
        #Pick the field to aggregate the lines together
        self.addParameter(QgsProcessingParameterField(
            self.INPUT_LINE_FIELD,'Line aggregation field',parentLayerParameterName=self.INPUT_LINE,type=QgsProcessingParameterField.Any,optional=True))
        
        #Polygons inputs
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_POLY,'Polygon layer', types=[QgsProcessing.TypeVectorPolygon],optional=True))

        #Pick the field to aggregate the polygons together
        self.addParameter(QgsProcessingParameterField(
            self.INPUT_POLY_FIELD,'Polygon aggregation field',parentLayerParameterName=self.INPUT_POLY,type=QgsProcessingParameterField.Any,optional=True))

        #Destination folder
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_FOLDER,'Output folder',createByDefault=True,
            defaultValue=os.path.join(os.path.dirname(QgsProject.instance().fileName()), "GPS", "ForUploadingToGPS").replace("\\", "/") + '/' + datetime.today().strftime("%Y%m%d") + '___Survey'))
                
    """
    #############################################################################################
    Bring in the user's input
    """

    #This is the part that runs and actually does the processing work
    def processAlgorithm(self, parameters, context, feedback: QgsProcessingFeedback):
        
        #Get the input points layer
        pointsSource = self.parameterAsSource(parameters, self.INPUT_POINT, context)
        if pointsSource:
            #The below gets the input layer such that the 'selected features only' feature actually works
            pointsLayer = QgsVectorLayer("Point?crs=" + pointsSource.sourceCrs().authid(), pointsSource.sourceName(), "memory")
            pointsLayer.dataProvider().addAttributes(pointsSource.fields())
            pointsLayer.updateFields()
            pointsLayer.dataProvider().addFeatures(list(pointsSource.getFeatures()))
            pointsLabel = self.parameterAsString(parameters, self.INPUT_POINT_LABEL, context)
            pointsDescription = self.parameterAsString(parameters, self.INPUT_POINT_DESCRIPTION, context)
            pointsAllFields = self.parameterAsBool(parameters, self.INPUT_POINT_ALL_FIELDS, context)
            pointsStyleIndex = self.parameterAsEnum(parameters, self.INPUT_POINT_SYMBOL, context)
            pointsStyle = pointStyles[pointsStyleIndex]

        #Get the input lines layer
        linesSource = self.parameterAsSource(parameters, self.INPUT_LINE, context)
        if linesSource:
            linesLayer = QgsVectorLayer("LineString?crs=" + linesSource.sourceCrs().authid(), linesSource.sourceName(), "memory")
            linesLayer.dataProvider().addAttributes(linesSource.fields())
            linesLayer.updateFields()
            linesLayer.dataProvider().addFeatures(list(linesSource.getFeatures()))
            linesFieldName = self.parameterAsString(parameters, self.INPUT_LINE_FIELD, context)
            
        #Get the input polygons layer
        polygonsSource = self.parameterAsSource(parameters, self.INPUT_POLY, context)
        if polygonsSource:
            polygonsLayer = QgsVectorLayer("Polygon?crs=" + polygonsSource.sourceCrs().authid(), polygonsSource.sourceName(), "memory")
            polygonsLayer.dataProvider().addAttributes(polygonsSource.fields())
            polygonsLayer.updateFields()
            polygonsLayer.dataProvider().addFeatures(list(polygonsSource.getFeatures()))
            polygonsFieldName = self.parameterAsString(parameters, self.INPUT_POLY_FIELD, context)
            
        #Create the output folder if it doesn't already exist
        destinationFolder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context).replace("\\",'/') + '/'
        if not os.path.exists(destinationFolder):
            os.makedirs(destinationFolder)
        
        #See how it goes and raise an exception if need be
        try:
            
            #Use the job name to name the files
            qgisProjectName = os.path.splitext(os.path.basename(QgsProject.instance().fileName()))[0]
            
            """
            #############################################################################################
            Points exporting to GPX
            """
            
            #Test to see if the points layer is in the project
            if pointsSource:
                
                #If the layer has features it exports a refactored gpx
                if pointsLayer.featureCount() > 0:
                    
                    #If the user wants to just dump all fields into the gpx
                    if pointsAllFields:
                        
                        #Get all field names except for fid
                        allFieldNames = [field.name() for field in pointsLayer.fields() if field.name().lower() != 'fid']

                        #Build a Field Calculator expression that is a massive case-when
                        expressionParts = []
                        for fieldName in allFieldNames:
                            #Wrap each CASE in coalesce to prevent NULL from breaking the string (whatever that means)
                            part = "coalesce(CASE WHEN \"{0}\" IS NOT NULL AND \"{0}\" != '-' THEN '{0}: ' || \"{0}\" || '\n' END,'')".format(fieldName)
                            expressionParts.append(part)

                        #Join everything into one expression string, with the || thing in between
                        pointsDescription = ' || '.join(expressionParts)

                        #Display the big ass parameter
                        feedback.pushInfo(pointsDescription)
                    
                    #Export the layer to gpx with the fields defined as such
                    processing.run("native:refactorfields", {'INPUT':pointsLayer,'FIELDS_MAPPING':[{'expression': 'left(to_string(' + pointsLabel + '),20)','length': 20,'name': 'name','type': 10,'type_name': 'text'},
                        {'expression': pointsDescription,'length': 0,'name': 'cmt','type': 10,'type_name': 'text'},
                        {'expression': "'" + pointsStyle + "'",'length': 20,'name': 'sym','type': 10,'type_name': 'text'}],
                        'OUTPUT':destinationFolder + qgisProjectName[:6] + '_' + pointsLayer.name().replace('/','') + '_GPX' + datetime.today().strftime("%Y%m%d") + '.gpx'}, feedback = feedback)
                        
                else:
                    feedback.reportError('The points layer is empty')
            
            """
            #############################################################################################
            Lines exporting to GPX
            """

            #Test to see if the lines layer is in the project
            if linesSource:
        
                #If it has features then
                if linesLayer.featureCount() > 0:
                    
                    #First up the lines are dissolved
                    #This is done because the ecologists want the minimum amount of features in their GPS devices, to save confusion
                    layerLinesDissolved = processing.run("native:dissolve", {'INPUT':linesLayer,'FIELD':[linesFieldName],'SEPARATE_DISJOINT':False,
                        'OUTPUT':QgsProcessing.TEMPORARY_OUTPUT}, feedback = feedback)['OUTPUT']
                    
                    #Handling for blank aggregation
                    if not linesFieldName:
                        linesFieldName = "''"
                    
                    outputLineGpx = destinationFolder + qgisProjectName[:6] + '_' + linesLayer.name() + '_GPX' + datetime.today().strftime("%Y%m%d") + '.gpx'
                    
                    #Refactor to put the code into the name field
                    #The name field is what the ecologist can see in their GPS
                    processing.run("native:refactorfields", {'INPUT':layerLinesDissolved,
                    'FIELDS_MAPPING':[{'expression': "left(" + linesFieldName + "  ||  ' ('  ||  num_geometries( @geometry)  ||  ')',20)",
                        'length': 20,'name': 'name','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'}],
                        'OUTPUT':outputLineGpx}, feedback = feedback)
                        
                    #Read the gpx
                    lineGpxFile = open(outputLineGpx).read()

                    #Add Garmin namespace
                    lineGpxFile = lineGpxFile.replace('xmlns="http://www.topografix.com/GPX/1/1"',
                        'xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3"')

                    #Add track color after each </name> of <trk>
                    lineGpxFile = lineGpxFile.replace('</name>',
                        '''</name>
        <extensions>
            <gpxx:TrackExtension>
                <gpxx:DisplayColor>Red</gpxx:DisplayColor>
            </gpxx:TrackExtension>
        </extensions>''')

                    # Overwrite the same file
                    with open(outputLineGpx, "w") as f:
                        f.write(lineGpxFile)

                else:
                    feedback.reportError('The lines layer is empty')
                    
            """
            #############################################################################################
            Polygons exporting to GPX
            """

            #Test to see if the polygons layer is in the project
            if polygonsSource:
        
                if polygonsLayer.featureCount() > 0:
                    
                    #Convert the polygons to lines, given that gpx files cannot accept polygons
                    layer_polyToLine = processing.run("native:polygonstolines", {'INPUT':polygonsLayer,'OUTPUT':QgsProcessing.TEMPORARY_OUTPUT}, feedback = feedback)['OUTPUT']
                    
                    layer_Dissolved = processing.run("native:dissolve", {'INPUT':layer_polyToLine,'FIELD':[polygonsFieldName],'SEPARATE_DISJOINT':False,
                        'OUTPUT':QgsProcessing.TEMPORARY_OUTPUT}, feedback = feedback)['OUTPUT']
                    
                    if not polygonsFieldName:
                        polygonsFieldName = "''"
                    
                    outputPolyGpx = destinationFolder + qgisProjectName[:6] + '_' + polygonsLayer.name().replace('/','') + '_GPX' + datetime.today().strftime("%Y%m%d") + '.gpx'
                    
                    processing.run("native:refactorfields", {'INPUT':layer_Dissolved,
                        'FIELDS_MAPPING':[{'expression': "left(" + polygonsFieldName + "  ||  ' ('  ||  num_geometries( @geometry)  ||  ')',20)",'length': 20,'name': 'name','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},],
                        'OUTPUT':outputPolyGpx}, feedback = feedback)

                    #Read the gpx
                    polyGpxFile = open(outputPolyGpx).read()

                    #Add Garmin namespace
                    polyGpxFile = polyGpxFile.replace('xmlns="http://www.topografix.com/GPX/1/1"',
                        'xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3"')

                    #Add track color after each </name> of <trk>
                    polyGpxFile = polyGpxFile.replace('</name>',
                        '''</name>
        <extensions>
            <gpxx:TrackExtension>
                <gpxx:DisplayColor>Red</gpxx:DisplayColor>
            </gpxx:TrackExtension>
        </extensions>''')

                    # Overwrite the same file
                    with open(outputPolyGpx, "w") as f:
                        f.write(polyGpxFile)
                    
                else:
                    feedback.reportError('The polygons layer is empty')
                    
        except BaseException as e:
            feedback.reportError(str(e))
        
        #Return nothing because you have to return something
        return {}
    """
    ###############################################################
    Final definitions of names etc
    """

    def name(self):
        return 'layers_to_gpx'

    def displayName(self):
        return 'Layers To GPX'

    def group(self):
        return 'NB Custom Scripts'

    def groupId(self):
        return 'nbcustomscripts'

    def createInstance(self):
        return LayersToGPX()
