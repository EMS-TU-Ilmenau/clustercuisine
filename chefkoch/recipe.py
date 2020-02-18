# -*- coding: utf-8 -*-

r"""
The recipe file entered by the user declares all the steps taken in the simulation,
i.e. functions, and the dependencies in form of exchanged data between the steps.
The Recipe Module concerning all classes and functions needed to parse a json file
into a recipe object and check integrity.
"""
# classes to put recipe json data into


from __future__ import unicode_literals
import os
import io
import platform
import json
import sys
sys.path.append('../../chefkoch/chefkoch')
# logs need to be imported this way to not write logs.logger all the time
from logs import *

# constants
# built-in functions that can be called as a simulation step inside a node
BUILT_INS = ["collect"]


class Recipe:
    """
    A recipe is the workflow representation of a simulation. It is struktured
    as a list of nodes of class Node. The nodes already contain information
    about the data flow and dependencies in the workflow, so there is not
    explicit representation of edges or dependencies needed.
    """
    nodes = []

    def __init__(self, nodelist):
        self.nodes = nodelist
        # Making sure, that nodelist is a list of type Node
        try:
            emptyNode = Node(
                "nodeName",
                {"i": "input"},
                {"o": "output"},
                "collect")
            self.nodes.append(emptyNode)
            self.nodes.pop()
        except Exception as exc:         # mit Klasse
            logger.exception(exc)
            #raise TypeError("""Class Recipe expects a list to be
            #    initialised with.""")

    def inputIntegrity(self):
        """
        Tests if there is exactly one incoming edge to every input.
        Warns, if there is no incoming edge. Excludes nodes from recipe,
        that have no incoming edge for a node or have uncomputable inputs
        because of missing inputs in parent nodes.
        Inputs:
             -
        Outputs:
            err         String. None if correct. Else error message.
            warn        String. None if correct. Else error message.
        """
        err = None
        warn = None
        # 1. make unique list of outputs
        outputs_of_all_nodes = []
        for node in self.nodes:
            for key in node.outputs:
                output = node.outputs[key]
                if output in outputs_of_all_nodes:
                    #  ("" if err is None else err) + "bla"
                    # overwrite exception class to generate warns
                    err = (("" if err is None else err) + 'The output ' +
                           output + ' of node ' + node.name +
                           ' has the same name as an output declared before. ')
                else:
                    outputs_of_all_nodes.append(output)
        # 2. see if inputs are from flavour, are file paths to existing files
        # or are in output list
        try_again = True
        while try_again:
            unreachable_nodes = []
            for node in self.nodes:
                nodeIsValid = True
                for key in node.inputs:
                    input = node.inputs[key]
                    # to do: Werte direkt zulassen, nicht nur ?ber flavour
                    # WARN schmei?en
                    # python logs verwenden: kein flavour, kein output, also
                    # interpretiert als string
                    # chef analyse (from log)
                    inputIsValid = False
                    prefix = os.path.splitext(input)[0]
                    extension = os.path.splitext(input)[1]
                    if (input in outputs_of_all_nodes or
                            prefix == 'flavour' or
                            extension == '.json'):
                        inputIsValid = True
                    else:
                        try:                # todo os.path os.isfile ?
                            with open(input) as f:
                                forget = file.readline(f)
                                inputIsValid = True
                        except IOError:
                            pass
                    if not inputIsValid:
                        nodeIsValid = False
                if not nodeIsValid:
                    unreachable_nodes.append(node)

        # 3. Delete unreachable nodes and unreachable outputs and do it again.
            try_again = (len(unreachable_nodes)>0)
            for node in unreachable_nodes:
                warn = (("" if warn is None else warn) + 'Node ' + node.name +
                        ' or one of its previous nodes has an invalid input' +
                        ' and therefore cannot be computed. ')
                for key in node.outputs:
                    output = node.outputs[key]
                    outputs_of_all_nodes.remove(output)

                # outputs_of_all_nodes.remove(node.outputs.values())
                # # <-- if remove can remove a list of objects
                # keys_to_remove = [val for val in node.outputs.values()
                # if val in output_of_all_nodes]
                # outputs_of_all_nodes = [oo for oo in outputs_of_all_nodes
                # if oo not in node.outputs.values()]
                self.nodes.remove(node)

        # 4. Loop until all nodes are reachable
        return err, warn

    def findCircles(self):
        """
        Makes list of all nodes, that have only flavour parameters as inputs.
        Then starts depth-first search for every root node. If there is a way
        back to a previously visited node, there is a warning about a circle.
        Inputs:
            none
        Outputs:
            err         String about circle or "" if everything is correct
        """
        rootNodes = []
        # 1. Make list of all nodes that only have flavour inputs.
        for node in self.nodes:
            isRootNode = True
            for key in node.inputs:
                input = node.inputs[key]
                if not input.startswith("flavour."):
                    isRootNode = False
                    break
            if isRootNode:
                rootNodes.append(node)

        logger.info("Root Nodes:")
        # 2. Start depth-first-search for every such node.
        for node in rootNodes:
            logger.info(node.name)
            nodesOnTheWay = []
            # do recursive depth-first search
            if self.recursiveDFS(node, nodesOnTheWay):
                return str("The recipe contains a circle reachable from " +
                           node.name)
        return ""

    def recursiveDFS(self, node, nodesOnTheWay):
        """
        Recursive Depth First Search finding circles.
        Inputs:
            node            The node, the DFS starts in.
            nodesOnTheWay   Previously visited nodes. If a node in there can
                            be visited by going deeper into the graph,
                            there is a circle.
        Outputs:
            bool            True if there is a circle. False elsewise.
        """
        namesOnTheWay = ""
        for nodeOTW in nodesOnTheWay:
            namesOnTheWay = namesOnTheWay + " " + nodeOTW.name
        logger.debug("Executing rDFS for " + node.name + " and " +
              namesOnTheWay)
        if node in nodesOnTheWay:
            logger.warn("The recipe contains a circle along " +
                        namesOnTheWay + node.name + " and can therefore" +
                        " not be executed.")
            return True
        nodesOnTheWay.append(node)
        # this only gets longer in deeper recursion levels
        # no need to bring nodes from deeper levels up.
        for key in node.outputs:
            output = node.outputs[key]
            # output might be used by several other nodes
            for nextNode in self.nodes:
                # to search for the values in a dict instead of their keys
                # we need to invert it
                invertedInputDict = dict(map(reversed, nextNode.inputs.items()))
                if output in invertedInputDict:
                    logger.debug("Taking the edge from " + node.name + " to " +
                          nextNode.name)
                    if self.recursiveDFS(nextNode, nodesOnTheWay):
                        return True # a circle was found
                    # else continue with next node
        # after all outgoing edges where tested, remove current node
        nodesOnTheWay.remove(node)    
        # if there is no circle from none of the outputs
        return False


class Node:
    """
    A node encapsules a simulation step within a recipe. The step can
    be realised by a python file, a sub-recipe or a built-in function.
    Each node also has a name, a dict of inputs and a dict of outputs.
    To the inputdict, the key is the same input name that the step takes,
    the value is where the input comes from. To the outputdict, the key
    is the name the step uses, the value is the name under which the
    output is available to other nodes in the recipe (the same name used
    as value in another inputdict).
    """
    def __init__(self, name, inputdict, outputdict, stepsource):
        # for empty name enter "" into recipe, unicode and string needed
        try:
            name_obj = Name(name)
            self.name = name_obj.name # Willi, ist das wirklich so gemeint?
        except TypeError as err:
            pass
        # testing the input to be delivered in a dict
        if not (isinstance(inputdict, dict)):
            raise TypeError('The input of node ' + str(name) +
                            ' must be of the format {\"name as in ' +
                            'step\": value, ...}')
            return
        self.inputs = inputdict
        # later replace strings by values in flavour?
        # testing the output to be delivered in a dict
        if not (type(outputdict) == dict):
            raise TypeError('The output of node ' + str(name) +
                            ' must be of the format {\"name as in ' +
                            'step\": value, ...}')
            return
        self.outputs = outputdict
        try:
            step_obj = StepSource(stepsource)
            self.step = step_obj.step
        except TypeError as err:
            pass

class Name:
    """
    Name convention for the name of a node.
    """
    def is_ascii(self, name):
        """
        Checks if string consists of only ascii characters.
        Inputs:
            name        String
        Outputs:
            is_ascii    Boolean. True if so.
        """
        return all(ord(c) < 128 for c in name)

    def __init__(self, name):
        is_unicode = False
        try:
            is_unicode = isinstance(name, unicode)
        except NameError as mimimi:
            # You are using python3 but don't worry. It works anyway.
            # logger.debug(mimimi)
            # logger.debug("You are using python 3, but don't worry, we make it work.")
            pass
        if not (isinstance(name, str) or is_unicode):
            raise TypeError('The name of a node must be a string.')
        if not self.is_ascii(name):
            raise ValueError('The name of a node must be ascii.')
        self.name = name


class StepSource:
    """
    Specifies the function to be executed inside a node in the recipe.
    """
    def __init__(self, stepsource):
    # testing if step is built-in or python function
        extension = os.path.splitext(stepsource)[1]
        if extension == ".py":
            self.step = stepsource
        elif extension == ".json":
            self.step = stepsource
        elif str(stepsource) in BUILT_INS:
            self.step = stepsource
            # done: research on assigning functions as attributes
            # (so that it can be accessed no matter where the object
            # is used)
        else:
            raise TypeError('Stepsource to node ' + str(name) +
                            ': ' + str(stepsource) +
                            '. Must be a Python file, another recipe ' +
                            'or a build-in function.')

class Flavour(dict):  # todo: class Flavour extends dictionary
    """
    The flavour file is the collection of all paramters needed for the simulation and all
    their values the simulation should be executed with. The goal is to find the best
    parameter combination. Paramter can have a contant value, a list of values or a range.
    They can also be files.
    """
    #self = {}

    #def __init__(self, paramlist):
    #    self.params = paramlist
        # Making sure that paramlist is a list of type Param

    #def __setitem__(self, key, value):
    #    self.params[key] = value
    #    return

    #def __getitem__(self, key):
    #    return self.params[key]

    def tostring(self):
        content = "The flavour file contains: "
        for key in self:
            content += "\n  " + str(key) + ": " + self[key].tostring()
        return content


class FileParamValue:
    """
    A possible value of a parameter of the simulation can be a file.
    """
    def __init__(self, filepath, key):
        logger.debug("Creating new FileParamValue")
        logger.debug("Filepath (dict): " + filepath)
        logger.debug("Key (dict): " + key)
        self.key = key
        logger.debug("Key: " + self.key)
        if os.path.isfile(filepath):
            self.file = filepath
            logger.debug("Filepath: " + self.filepath)
        else:
            logger.warn("The following filepath does not exist: " + filepath)
            raise IOError("The file " + filepath + " does not exist.")
            return

    def tostring(self):
        """
        Returns string that can be printed.
        """
        content = "Value is following file: \n  "
        content+= self.filename + "\n  Key: " + self.key
        return content


class Param:
    """
    A parameter with all values attached to it.
    """
    values = []
    file = None

    def appendFileParam(self, entry):
        """
        Appends a file parameter given in the JSON data to the Param.values list.
        Inputs:
            entry       dict with fields type, file and key
        Outputs:
            -
        """
        logger.debug("Why the heck does it never enter appendFileParam?" + str(entry))
        try:
            newValue = FileParamValue(entry['file'], entry['key'])
            self.values.append(newValue)
            logger.debug("Appending " + str(newValue) + newValue.tostring())
        except KeyError as err:
            # todo: different possible exceptions
            logger.exception("Either the file or the key field of the entry are missing.")
            print("TODO: catch " + str(err))
            pass
        except IOError as err:
            logger.warn(err)
            pass

    def appendValuesFromRange(self, entry):
        """
        Appends all values within a range given in the JSON data to Param.values
        Inputs:
            entry       dict with fields start, stop and step.
        Outputs:
            -
        """
        logger.debug("More values are given by a range.")
        try:
            i = entry['start']
            # add all values within range
            while i <= entry['stop']:
                logger.debug("Adding value " + str(i))
                self.values.append(i)
                i = i + entry['step']
                # alternative: value = ParameterRange(start, stop, stepsize)
        except Exception as err:
            logger.exception(err)
            print("TODO: catch " + err)
            return

    def appendEntry(self, entry):
        """
        Appends an entry within the JSON data received from the flavour file.
        Inputs:
            entry       mat-file or range or any other value
        Outputs:
            -
        """
        try:
            logger.debug("It is of type " + entry['type'])
            if entry['type'] == 'mat-file': # make more file cases here
                logger.debug("The value of the parameter is a mat-file.")
                try:
                    self.appendFileParam(entry)
                except IOError as err:
                    logging.warn("The entry " + entry + " is not included as parameter.")
                except Exception as typo:
                    logger.debug(typo)
                    print(typo)
            elif entry['type'] == 'range':
                self.appendValuesFromRange(entry)
        except TypeError as typo:
            if type(entry) in [str, int, float, bool, unicode]:
                # todo: python3 does not know unicode and python2 needs unicode
                # todo: allow everything else by default,
                # value could also be a list
                logger.debug("Appending " + str(entry))
                self.values.append(entry)
            else:
                raise TypeError('The flavour file holds an entry that is not supported.')


    def __init__(self, name, entry):
        """
        Creates a new paramter from the JSON data gotten from the flavour file.
        Inputs:
            name        name as provided as in flavour file
            entry       if the falvour file was a dict, it was flavour['name']
        Outputs:
            -
        """
        logger.debug("Creating a new parameter " + str(name))
        self.name = name
        if type(entry) is not list: # a single value so to say
            logger.debug("It has a single value: " + str(entry))
            self.appendEntry(entry)    
        else:
            logger.debug("It has more than one value.")
            for sub_entry in entry: # the entry in the json file
                self.appendEntry(sub_entry)
        logger.debug("Fin.")    


    def tostring(self):
        """
        Returns a printable and formatted string that shows the Parameter
        and its values.
        Inputs:
            -
        Outputs:
            -
        """
        content = "Parameter name: " + self.name
        for value in self.values:
            if type(value) is FileParamValue:
                content += "\n  " + value.tostring()
            else:
                content += "\n  " + str(value)
        return content


def readrecipe(filename):
    """
    Opens a JSON file and parses it into a recipe object. Then outputs
    the data inside the recipe.
    Inputs:
        filename    file path string
    Outputs:
        recipe      object of type recipe
        err         error message string
    """
    jsonData, err = openjson(filename)
    if err is not None:
        logger.error(err)
        return (None, err)
    recipe, err = jsonToRecipe(jsonData)
    if err is not None:
        logger.error(err)
        return (None, err)
    printRecipe(recipe)
    err, warn = recipe.inputIntegrity()
    if err is not None:
        logger.error(err)
        return(None, err)
    if warn is not None:
        logger.warning(warn)
    err = recipe.findCircles()
    if err is not "":
        logger.error(err)
        return (None, err)
    return (recipe, None)


def readflavour(filename):
    """
    Opens a JSON file and parses it into a flavour object. Then outputs
    the data inside the flavour file.
    Inputs:
        filename    file path string
    Outputs:
        flavour     object of type flavour. if error occured, it holds the error
    """
    jsonData, err = openjson(filename)
    if err is not None:
        logger.error(err)
        return err
    flavour, err = jsonToFlavour(jsonData)
    if err is not None:
        logger.error(err)
        return err
    #print(flavour.tostring())
    # todo: input Integrity checks
    return flavour


def openjson(filename):
    """
    Opens a JSON file, makes sure it is valid JSON and the file exists
    at the given path. Loads the whole file at once. File should there-
    fore not be too big.
    Inputs:
        filename    string
    Outputs:
        data        dict or list depending on JSON structure
        err         Error message string, None if everything worked fine
    """
    if not os.path.isfile(filename):
        return (None, "The file path or file name is incorrect.")
    with open(filename) as f:
        try:
            data = json.load(f)
            # That's the whole file at once. Hope files dont get too big
        except ValueError as err:
            return (None, "This is no valid JSON file. Try deleting comments.")
        
    return (data, None)


def jsonToRecipe(data):
    """
    Takes a dictionary or list of interpreted JSON and parses it into an object
    of class Recipe.
    Inputs:
        data        dict or list depending on the outer structure of JSON file
    Outputs:
        recipe      object of class Recipe
        err         Error message string, None if everything worked fine
    """
    if not isinstance(data, dict):
        return (None, 'Function jsonToRecipe expects dictionary as input.')
    recipe = Recipe([])
    for node in data['nodes']:
        try:
            newNode = Node(
                node['name'],
                node['inputs'],
                node['outputs'],
                node['stepsource'])
            recipe.nodes.append(newNode)
        except TypeError as errorMessage:
            return (None, errorMessage)
        except Exception as err:
            return (None, 'Error while parsing json data into recipe object.')

    return (recipe, None)


def jsonToFlavour(data):
    """
    Turns data loaded from a json file into a flavour object.
    Inputs:
        data        dict or list depending on json file.
    Outputs:
        flavour     object of class flavour
        err         Error message string, None if everything worked fine
    """
    if not isinstance(data, dict):
        return(None,'Function jsonToFlavour expects a dictionary as input.')
    flavour = Flavour({})
    for param in data:
        try:
            newParam = Param(
                param,      # name which is also key
                data[param] # indifferent shit will be handled in Param init
                )
            flavour[param] = newParam   # new entry to dict
        except TypeError as errorMessage:
            return (None, errorMessage)
        except Exception as err:
            logger.exception(err)
            return (None, 'Error while parsing json data into flavour object.')

    return (flavour, None)

def printRecipe(recipe):
    """
    Prints the information held inside a Recipe object.
    Inputs:
        recipe      object of class Recipe
    Outputs:
        console output
    """
    print(recipe.nodes)
    for node in recipe.nodes:
        print("Nodename:")
        print("  " + str(node.name))
        print("Inputs:")
        for input in node.inputs:
            print("  " + input + "\t" + str(node.inputs[input]))
        print("Outputs:")
        for output in node.outputs:
            print("  " + output + "\t" + str(node.outputs[output]))
        print("Executes:")
        print("  " + str(node.step))
        print("\n")
