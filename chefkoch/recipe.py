# -*- coding: utf-8 -*-
# Copyright 2019 Christoph Wagner
#     https://www.tu-ilmenau.de/it-ems/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

r"""
The recipe file entered by the user declares all the steps taken in the
simulation and the dependencies in form of exchanged data
between the steps. The Recipe module holds all classes and functions
needed to parse a YAML file into a recipe object and check integrity.
"""

from __future__ import unicode_literals
import os
import io
import platform
import json
import sys
import warnings
import itertools
import hashlib
import copy
from graph import Graph
from collections import ChainMap
from typing import Dict, Any

import chefkoch.fridge

from chefkoch.container import YAMLContainer, JSONContainer, dict_hash

# logs need to be imported this way to not write logs.logger all the time
# from .logs import *


# constants
# built-in functions that can be called as a simulation step inside a node
BUILT_INS = ["collect"]


class Plan:
    def __init__(self, recipe, *targets, fridge=None):
        """
        Initialize Plan Object over a given recipe and calculation targets
        Parameters
        ----------
        recipe:  recipe object
        targets: calculation targets given as string (name of the node),
                 int (list index of the node in recipe object)
                 or node object
        """
        self.nodes = []
        self.items = []
        self.magisNodes = []
        self.flavours = {}
        self.variants = JSONContainer()

        # append fridge
        if fridge is not None:
            self.fridge = fridge

        # if no targets are given fill with default
        if len(targets) == 0 or targets[0] is None:
            targets = self.fillTargets(recipe)

        # normalize targets
        #   if target is itemnode --> get
        for target in targets:
            if target[:4] != "item":
                for targetitem in recipe.graph.nodes(from_node=target):
                    self.magisNodes.extend(
                        self.getMagisGraphNodes(recipe, targetitem)
                    )
            else:
                self.magisNodes.extend(self.getMagisGraphNodes(recipe, target))
        self.magisGraph = recipe.graph.subgraph_from_nodes(self.magisNodes)
        for node in self.magisNodes:
            if node[:4] == "item":
                self.items.append(node[5:])
            else:
                self.nodes.append(node)

        if fridge is not None:
            # self.planIt()
            self.getFlavours()
        self.makeNormalGraph()

        self.startingItems = list(
            x[5:] for x in self.magisGraph.nodes(in_degree=0)
        )

        for node in self.graph.nodes(out_degree=0):
            self.buildVariants(node)

        self.prioritys = {}
        self.assertPriority()
        self.joblist = self.makeJoblist()
        print(None)
        self.makeMaps()

    def makeMaps(self):
        """
        creates and returns a map(dict) containing
        information where a step finds its inputs
        """
        map = {}
        for nodeName in self.graph.nodes():
            node = self.graph.node(nodeName)
            # for input in g.inputs:
            for inNodeName in self.graph.nodes(to_node=nodeName):
                inNode = self.graph.node(inNodeName)
                # for inNodeInput in inNode.inputs:
                for inputKey, inputValue in node.inputs.items():
                    print(inputKey)
                    if inputValue == inNode.outputs["result"]:
                        map[nodeName] = {inputKey: inNodeName}

        return map

    def completeJoblist(self):
        for priority in self.joblist:
            shelf = self.fridge.getShelf(priority[0][0])
            for job in priority:
                job[1] = shelf.items[job[1].data["hash"]]
                pass

    def makeJoblist(self):
        """
        Creates priority based joblist by iterating every
        node and its variants.

        Returns
        -------
        joblist(list of list of ResultItem)
        """
        joblist = [[] for i in range(len(self.prioritys))]
        for nodeName, variantlist in self.variants.data.items():
            for variant in variantlist.items():
                # e = self.prioritys[nodeName]
                # ee = joblist[e]
                joblist[self.prioritys[nodeName]].append(
                    self.makeJob(variant, nodeName)
                )
        return joblist

    def makeJob(self, nodeVariant, nodeName):
        """
        Creates ResultItem for given variant of a node

        Parameters
        ----------
        nodeVariant(Tuple(Hash(int), inputs(dict)))
            Necessary information about variant
        nodeName(str)
            Name of the associated Node

        Returns
        -------
        ResultItem
        """
        return [
            nodeName,
            JSONContainer(
                data={
                    "hash": nodeVariant[0],
                    "inputs": nodeVariant[1],
                    "priority": self.prioritys[nodeName],
                }
            ),
        ]

    def getJoblist(self):
        """
        Returns a list of jobs splittet in different prioritys

        Returns
        -------
        joblist(list of list of ResultItem)
        """
        return self.joblist

    def assertPriority(self, node=None, priority=-1):
        """
        Calculates priority for every node in graph "below" given node.

        Parameters
        ----------
        node(str), default: 'None':
            Name of the node. Can be 'None' for calculating all prioritys
        priority(int): default: -1:
            Starting priority - 1
        """
        if node is None:
            for endNode in self.graph.nodes(out_degree=0):
                self.assertPriority(endNode, priority + 1)
        else:
            if node in self.prioritys.keys():
                if self.prioritys[node] < priority:
                    self.prioritys[node] = priority
            elif node not in self.prioritys.keys():
                self.prioritys[node] = priority
            # else:
            for child in self.graph.nodes(to_node=node):
                self.assertPriority(child, priority + 1)

    def isItemNode(self, node):
        """
        Checks if a node has the prefix "item."
        Parameters
        ----------
        node(str):
            Name of the node
        """

        if node[0:5] == "item.":
            return True
        else:
            return False

    def makeNormalGraph(self):
        """
        Removes Itemnodes from self.magisGraph and directly connects the
        surrounding nodes producing the self.graph object
        Parameters
        ----------
        """
        self.graph = self.magisGraph.copy()
        # self.graph = copy.deepcopy(self.magisGraph)
        for node in self.graph.nodes():
            if self.isItemNode(node):
                ends = self.graph.nodes(from_node=node)
                starts = self.graph.nodes(to_node=node)
                for x in starts:
                    for y in ends:
                        self.graph.add_edge(x, y)
                self.graph.del_node(node)

    def buildVariants(self, node):
        """
        Create variants in 'self.variants' for specific node.
        Variants for all nodes "before" the wanted one will
        be calculated also.
        Parameters
        ----------
        node(str):
            name of the node whose variants should be calculated
        """
        children = self.graph.nodes(to_node=node)
        additionalToInput = {}

        if len(children) > 0:  # and len(self.variants) > 0:
            if node not in self.variants:
                childs = {}  # inputs in form of child nodes
                inputs = {}  # direct inputs from resources/flavours
                ret = {}
                for child in children:
                    self.buildVariants(child)
                    # if child in self.variants:
                    # inputs[child] = self.variants[child]
                    childs[child] = list(
                        child + "/" + str(x) for x in self.variants[child]
                    )
                for input in self.graph.node(node).inputs.values():
                    if input in self.flavours.keys():
                        inputs[input] = {
                            x: None for x in self.flavours[input].items
                        }
                    elif input in self.startingItems:
                        shelf = self.fridge.getShelf(input)
                        resourceItemHash, = shelf.items.keys()
                    inputs[input] = {"Resource/" + input + "/" + str(resourceItemHash)}
                accordance = self.checkAccordance(childs, list(inputs))
                accorded = {}
                if len(accordance) > 0:
                    for accordanceKey in accordance.keys():
                        accorded[accordanceKey] = self.matchInputs(
                            accordanceKey,
                            self.variants,
                            accordance[accordanceKey],
                        )
                else:
                    inputs.update(childs)

                for input in accorded:
                    for inputValue in accorded[input]:
                        inputs[input][inputValue] = {}
                crossed = list(itertools.product(*list(inputs.values())))

                for c in crossed:
                    k = tuple(inputs.keys())
                    value = {k[i]: c[i] for i in range(len(k))}
                    ret[dict_hash(value)] = value
                for item in ret.items():
                    for child in children:
                        for variant in self.variants[child].items():
                            x = variant[1]
                            # x1 = set(x)
                            y = item[1]
                            if variant[1].items() <= item[1].items():
                                # if variant[1] in item[1]:
                                pass
                            if (
                                variant[1] == item[1]
                            ):  # or variant[1] in item[1]:
                                ret[item[0]][child] = (
                                    child + "/" + str(variant[0])
                                )
                                # ret[item[0]].append(
                                #     {child: child + "/" + str(variant[0])}
                                # )
                                break
                            else:
                                notFalse = False
                                for v in variant[1]:
                                    if v in item[1]:
                                        notFalse = True
                                        break
                                if notFalse:
                                    ret[item[0]][child] = (
                                        child + "/" + str(variant[0])
                                    )
                                    # ret[item[0]].append(
                                    #     {child: child + "/" + str(variant[0])}
                                    # )
                                break

                self.variants[node] = self.reHash(ret)

                # print(inputs)
        elif len(children) == 0:
            # self.variants[node] = self.flavours[node].items
            inputs = {}
            ret = {}
            # a = self.graph.node(node)
            for input in self.graph.node(node).inputs.values():
                if input in self.flavours:
                    inputs[input] = self.flavours[input].items
                else:
                    shelf = self.fridge.getShelf(input)
                    resourceItemHash, = shelf.items.keys()
                    inputs[input] = {"Resource/" + input + "/" + str(resourceItemHash)}

            crossed = list(itertools.product(*list(inputs.values())))
            for c in crossed:
                k = tuple(inputs.keys())
                value = {k[i]: c[i] for i in range(len(k))}
                ret[dict_hash(value)] = value
            self.variants[node] = ret
            pass

    def reHash(self, dict):
        """
        Recalculate and reassign hashes as keys to values of a dict
        Parameters
        ----------
        dict(dict):
            dictionary whose keys should be replaced by hashes
            or which hashes should be recalculated
        """
        # ret = {}
        ret2 = {}
        # for value in dict.values():
        #     for x in value:
        #         c = (list(x.values()))[0]
        #     c = tuple(list(x.values())[0] for x in value)
        #     k = tuple(list(x.keys())[0] for x in value)
        #     ret[hash((k, c))] = value

        for value in dict.values():
            ret2[dict_hash(value)] = value

        return ret2

    def matchInputs(self, input, data, map):
        """
        Matches the variants of the same inputs from child nodes and direct
        inputs with help of a given map
        """
        ret = {}
        if len(map) > 0:
            for key in map.keys():
                if map[key] == input:
                    for hashkey in data[key]:
                        n = data[key][
                            hashkey
                        ]  # dict(ChainMap(*data[key][hashkey]))
                        if n[input] in ret:
                            ret[n[input]].append(key + "/" + str(hashkey))
                        else:
                            ret[n[input]] = [key + "/" + str(hashkey)]
                        # print(hashkey)
                else:
                    ret = self.matchInputs(input, data[map[key]], map[key])
        return ret

    def checkAccordance(self, childdict, inputlist):
        """
        Checks and maps if the inputs of the children of a
        node and the nodes inputs are matching
        """
        accordance = {}
        for child in list(childdict):
            for input in inputlist:
                if child == input:
                    accordance[child] = child
            x = self.variants[child]
            # z = next(iter(x))
            # y = x[z]
            # if
            if x is not None:
                y2 = x[next(iter(x))]
                e = self.checkAccordance(y2, inputlist)
                if e != {}:
                    for input in inputlist:
                        if input in e:
                            accordance[input] = {child: e[input]}
        return accordance

    def getFlavours(self):
        for node in self.magisNodes:
            if node[5:] in self.fridge.shelves:
                # print(type(self.fridge.shelves[node[5:]]))
                # x = type(self.fridge.shelves[node[5:]])
                if (
                    type(self.fridge.shelves[node[5:]])
                    == chefkoch.fridge.FlavourShelf
                ):
                    # self.flavours.append(fridge.shelfs[node[5:]])
                    self.flavours[node[5:]] = self.fridge.shelves[node[5:]]
                    self.magisGraph.add_node(
                        node, self.fridge.shelves[node[5:]]
                    )

    # def planIt(self):
    #     for self.magisGraph

    def fillTargets(self, recipe):
        targets = []
        for endnode in recipe.graph.nodes(out_degree=0):
            targets.append(endnode)
        return targets

    def getItems(self):
        """
        Returns every item which is an input or output of a node
        :return: list of String
        """
        return self.items

    def getMagisGraphNodes(self, recipe, target):
        """
        Creates a list of nodes needed to calculate the target object
        :param recipe: recipe object
        :param target: string (name of the target node)
        :return: list of nodes
        """
        magisNodes = []
        for startingnode in recipe.graph.nodes(in_degree=0):
            print(startingnode, type(startingnode))
            print(recipe.graph.all_paths(startingnode, target))
            for liste in recipe.graph.all_paths(startingnode, target):
                magisNodes.extend(liste)
        return magisNodes


class Recipe:
    """
    A recipe is the workflow representation of a simulation. It is struktured
    as a list of nodes of class Node. The nodes already contain information
    about the data flow and dependencies in the workflow, so there is not
    explicit representation of edges or dependencies needed.
    """

    def __init__(self, magisNodes):
        """
        Initialises a recipe by appending the `magisNodes` to `nodes`.
        Parameters
        ------------
        magisNodes (Node[]):
            list of simulation steps as Node[]
        """
        self.nodes = magisNodes
        self.graph = Graph()
        self.makeGraph()
        # TODO: Making sure, that magisNodes is a list of type Node
        # TODO: Therefore initialise each Node in magisNodes as an
        # instance of class Node.

    def __getitem__(self, item):
        """
        :param item:
        :return:
        """
        if type(item) == int:
            return self.nodes[item]
        if type(item) == str:
            for node in self.nodes:
                if node.name == item:
                    return node

    def getPrerequisits(self, item):
        """
        Returns all nodes required to calculate a given item of the recipe
        :param item:
        :return: List of nodes
        """
        ret = []
        for previousNode in self.graph.nodes(to_node=item):
            ret.append(previousNode)
            ret.append(self.getPrerequisits(previousNode))
        return ret

    def inputIsValid(self, input):
        """
        Checks if a given input name is valid. An input is valid if it
        can be found either in the flavour file or is a file itself.
        It is also valid if it is an output name of another node, but this
        will not be checked.
        Parameters
        ----------
        input (str):
            The input that is to be tested
        Returns
        -------
        True if the input is valid.
        """
        if os.path.isfile(input):
            return True
        prefix = os.path.splitext(input)[0]
        if prefix == "flavour":
            return True
        else:
            return False

    def inputIntegrity(self):
        """
        Tests if there is exactly one incoming edge to every input.
        Warns, if there is no incoming edge. Excludes nodes from recipe,
        that have no incoming edge for a node or have uncomputable inputs
        because of missing inputs in parent nodes.
        Raises
        -------
        NameError:
            If two or more outputs share the same name.
        """
        # 1. make unique list of outputs
        outputs_of_all_nodes = set([])
        for node in self.nodes:
            node_outputs = set(node.outputs.values())
            # & is the intersection of sets
            if len(node_outputs & outputs_of_all_nodes) > 0:
                raise NameError(
                    "The output "
                    + str(node_outputs & outputs_of_all_nodes)
                    + " of node "
                    + node.name
                    + " has the same name as an output declared before. "
                )
            else:
                outputs_of_all_nodes.update(node_outputs)
        if len(self.graph.components()) > 1:
            raise ImportError(
                "One or more Nodes are not " "reachable from the others"
            )

        # 4. Loop until all nodes are reachable
        return None, None

    ########################

    def makeGraph(self):
        """
        Builds a Graph according to the recipe nodes saved in self.nodes
        with inputs/outputs presented as node with "item.[input/output name]"
        """
        for node in self.nodes:
            print("adding node: " + node.name)
            self.graph.add_node(node.name, node)
            for input in node.inputs.values():
                if "item." + input not in self.graph:
                    print("adding input: " + "item." + input)
                    self.graph.add_node("item." + input)
                self.graph.add_edge("item." + input, node.name)
            for output in node.outputs.values():
                if "item." + output not in self.graph:
                    print("adding output: " + "item." + output)
                    self.graph.add_node("item." + output)
                self.graph.add_edge(node.name, "item." + output)

        print(self.graph.to_dict())


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

    def __init__(self, name, inputdict, outputdict, stepsource, steptype):
        """
        Initializes a node of the recipe. A node represents a simulation
        step.
        Parameters
        ----------
        name (str):
            Name of the simulation step.
        inputdict (dict):
            Dictionary of all inputs needed to execute this step.
        outputdict (dict):
            Dictionary of all outputs of the simulation step.
        stepsource (str):
            Information on how to execute this step.
        Raises
        ------
        TypeError:
            If the input or output of a node are not given as a dict.
        """
        # for empty name enter "" into recipe
        # unicode and string needed
        # try:
        #     name_obj = Name(name)
        #     self.name = name_obj.name  # Willi, ist das wirklich so gemeint?
        # except TypeError as err:
        #     pass
        # testing the input to be delivered in a dict
        if not (isinstance(inputdict, dict)):
            raise TypeError(
                "The input of node "
                + str(name)
                + ' must be of the format {"name as in'
                + ' step": value, ...}'
            )
            return
        self.name = name
        self.inputs = inputdict
        # later replace strings by values in flavour?
        # testing the output to be delivered in a dict
        if not (type(outputdict) == dict):
            raise TypeError(
                "The output of node "
                + str(name)
                + ' must be of the format {"name as in '
                + 'step": value, ...}'
            )
            return
        self.outputs = outputdict
        # step_obj = StepSource(stepsource)
        self.step = stepsource
        self.type = steptype
        # todo abort in higher level and ignore whole node


class Name:
    """
    Name convention for the name of a node inside the recipe.
    """

    def __init__(self, name):
        """
        Takes a string or unicode and saves it if it is pure ascii.
        Parameters
        ----------
        name (str or unicode):
            Name to be checked and saved
        Raises
        ------
        TypeError:
            If `name` is has another type.
        ValueError:
            If `name` contains non-ascii characters.
        """
        is_unicode = False
        try:
            is_unicode = isinstance(name, unicode)
        except NameError as mimimi:
            logger.debug(mimimi)
            logger.debug(
                "You are using python 3, " "but don't worry, we make it work."
            )
            """
            pass
        if not (isinstance(name, str) or is_unicode):
            raise TypeError("The name of a node must be a string.")
        if not self.is_ascii(name):
            raise ValueError("The name of a node must be ascii.")
        self.name = name"""

    def is_ascii(self, name):
        """
        Checks if string consists of only ascii characters.
        Parameters
        ----------
        name (str or unicode):
            string
        Returns
        -------
        `True`, if name only contains ascii characters.
        """
        return all(ord(c) < 128 for c in name)


def readRecipe(dict):
    """
    Opens a YAML file and parses it into a recipe object. Then outputs
    the data inside the recipe.
    Parameters
    ----------
    filename (str):
        file path
    Returns
    -------
    Object of class Recipe
    :rtype: Recipe
    """

    recipe = dictToRecipe(dict)
    recipe.makeGraph()
    if recipe.graph.has_cycles():
        raise Exception("There is a Cycle in your recipe, please check")
    recipe.inputIntegrity()
    # recipe.findCircles()
    # printRecipe(recipe)
    return recipe


def dictToRecipe(data):
    """
    Takes a dictionary or list of interpreted YAML
    and parses it into an object of class Recipe.
    Parameters
    ----------
    data (dict or list):
        dict or list depending on the outer structure of YAML file
    Returns
    -------
    recipe - object of class Recipe \n
    :rtype: Recipe
    Raises
    -------
    TypeError:
        If data ist not of type dictionary.
    Exception:
        Error while parsing YAML data into recipe object.
    """
    if (
        not isinstance(data, dict)
        and not isinstance(data, YAMLContainer)
        and not isinstance(data, JSONContainer)
    ):
        raise TypeError("Function dictToRecipe expects dictionary as input.")
    recipe = Recipe([])
    for node in data.items():
        # print("node: ", node[0], node[1], " ", type(node[0]), len(node))
        # #, node.inputs, node.outputs)
        try:
            newNode = Node(
                node[0],
                node[1]["inputs"],
                node[1]["outputs"],
                node[1]["resource"],
                node[1]["type"],
            )
            recipe.nodes.append(newNode)
        except KeyError as err:
            raise KeyError("Error while parsing data into recipe object.")

    return recipe


def printRecipe(recipe):
    """
    Prints the information held inside a Recipe object to the console.
    Parameters
    ----------
    recipe (Recipe):
        object of class Recipe
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
