# -*- coding: utf-8 -*-
# This file holds unit tests for all functions inside the chefkoch module to
# ease the development process.
# Execute this file by typing into a linux console in same directory:
# python3 -m unittest test_chefkoch
# subtests are only available from python 3.4 on
# (maybe test_chefkoch.py depending on python and linux version)

import os
import unittest
import sys
sys.path.append('../chefkoch')
import recipe as backbone
import chefkoch

# todo: Konsultiere Fabian

class TestChefkoch(unittest.TestCase):

    def test_readrecipe(self):
        result, err = chefkoch.readrecipe('../recipe.json')
        self.assertIsNone(err)

class TestRecipe(unittest.TestCase):

    def test_openjson(self):
        # test 1: valid JSON recipe file.
        with self.subTest("test 1: Valid JSON recipe file."):
            result, err = backbone.openjson('../recipe.json')
            self.assertTrue(isinstance(result, dict))
            self.assertIsNone(err)
            self.assertEqual(result['nodes'][1]['name'], "prisma_volume")

        # test 2: broken JSON recipe file.
        with self.subTest("test 2: broken JSON recipe file."):
            result, err = backbone.openjson("../broken_for_testcase.json")
            self.assertEqual(
                err,
                "This is no valid JSON file. Try deleting comments.")
            self.assertIs(result, None)

        # test 3: file path wrong/ file does not exist
        with self.subTest("test 3: file path wrong/ file does not exist"):
            result, err = backbone.openjson("NoFileHere.json")
            self.assertEqual(err, "The file path or file name is incorrect.")
            self.assertIsNone(result)


    def test_jsonToRecipe(self):
        # test 1: Not giving a dict as input to jsonToRecipe
        with self.subTest("test 1: Not giving a dict as input to jsonToRecipe"):
            result, err = backbone.jsonToRecipe(None)
            self.assertIs(result, None)
            self.assertEqual(
                err,
                'Function jsonToRecipe expects dictionary as input.')

        # test 2: correct format with additional information still works
        with self.subTest("test 2: correct format with additional information still works"):
            data = {
                "nodes": [{
                    "name": "rectangle_area",
                    "inputs": {"d": "flavour.d", "b": "flavour.b"},
                    "unneccessary": "and of no interest",
                    "outputs": {"a": "area"},
                    "stepsource": "rectangle_area.py"
                }]
            }
            result, err = backbone.jsonToRecipe(data)
            self.assertIsInstance(result, backbone.Recipe)
            self.assertIsNone(err)
            self.assertEqual(result.nodes[0].inputs['b'], "flavour.b")

        # test 3: incorrect format
        with self.subTest("test 3: incorrect format"):
            data = {
                "nodes": [{
                    "name": "rectangle_area",
                    "missing": {},
                    "outputs": {"a": "area"},
                    "stepsource": "rectangle_area.py"
                }]
            }
            result, err = backbone.jsonToRecipe(data)
            self.assertIsNone(result)
            self.assertEqual(err, 'Error while parsing json data into recipe object.')

        # test 4: Annoying the Node class:
        # list of inputs is interpreted as value for parameter "a"
        with self.subTest("list of inputs is interpreted as value for parameter \"a\""):
            data = {
                "nodes": [{
                    "name": "fancy",
                    "inputs": {"a": ["first", "second"]},
                    "outputs": {"a": "area"},
                    "stepsource": "collect"
                }]
            }
            result, err = backbone.jsonToRecipe(data)
            self.assertIsNotNone(result)
            self.assertIsNone(err)

        # test 4: Annoying the Node class
        with self.subTest("test 4: Annoying the Node class"):
            data = {
                "nodes": [{
                    "name": "fancy",
                    "inputs": {"a": "first"},
                    "outputs": {"a": "area"},
                    "stepsource": "no_build-in_function"
                }]
            }
            result, err = backbone.jsonToRecipe(data)
            self.assertIsNone(result)
            self.assertIsNotNone(err)

        # todo: versions of var data in object with expected result
        # and err value attached to it and loop for test execution!

    def test_inputIntegrity(self):
        # recipe with two outputs with same name
        with self.subTest("recipe with two outputs with same name"):
            data = {
                "nodes": [{
                    "name": "A",
                    "inputs": {},
                    "outputs": {"a": "doppleganger"},
                    "stepsource": "source.py"
                }, {
                    "name": "B",
                    "inputs": {},
                    "outputs": {"b": "doppleganger"},
                    "stepsource": "source.py"
                }]
            }
            recipe, err = backbone.jsonToRecipe(data)
            self.assertIsNone(err)
            err, warn = recipe.inputIntegrity()
            self.assertTrue(str(err).startswith('The output'))
            self.assertIsNone(warn)

        # recipe that should work correctly
        with self.subTest("recipe that should work correctly"):
            data = {
                "nodes": [{
                    "name": "A",
                    "inputs": {"a": "flavour.a", "b": "flavour.b"},
                    "outputs": {"c": "outOfA"},
                    "stepsource": "somesource.py"
                }, {
                    "name": "B",
                    "inputs": {"d": "flavour.d", "e": "flavour.e"},
                    "outputs": {"f": "outOfB"},
                    "stepsource": "source.py"
                }, {
                    "name": "C",
                    "inputs": {"g": "outOfA", "h": "outOfB"},
                    "outputs": {"i": "outOfC"},
                    "stepsource": "source.py"
                }, {
                    "name": "D",
                    "inputs": {"toBeCollected": "outOfC", "by": "flavour.e"},
                    "outputs": {"k": "collected"},
                    "stepsource": "collect"
                }]
            }
            recipe, err = backbone.jsonToRecipe(data)
            self.assertIsNone(err)
            err, warn = recipe.inputIntegrity()
            self.assertIsNone(err)
            self.assertIsNone(warn)
            self.assertEqual(len(recipe.nodes), 4)

        # recipe that has an unreachable node C that also makes D unreachable
        with self.subTest("recipe that has an unreachable node C that also makes D unreachable"):
            data = {
                "nodes": [{
                    "name": "A",
                    "inputs": {"a": "flavour.a", "b": "flavour.b"},
                    "outputs": {"c": "outOfA"},
                    "stepsource": "somesource.py"
                }, {
                    "name": "B",
                    "inputs": {"d": "flavour.d", "e": "flavour.e"},
                    "outputs": {"f": "outOfB"},
                    "stepsource": "source.py"
                }, {
                    "name": "C",
                    "inputs": {"g": "outOfA", "h": "unreachable"},
                    "outputs": {"i": "outOfC"},
                    "stepsource": "source.py"
                }, {
                    "name": "D",
                    "inputs": {"toBeCollected": "outOfC", "by": "flavour.e"},
                    "outputs": {"k": "collected"},
                    "stepsource": "collect"
                }]
            }
            recipe, err = backbone.jsonToRecipe(data)
            self.assertIsNone(err)
            err, warn = recipe.inputIntegrity()
            self.assertIsNone(err)
            self.assertIsNotNone(warn)
            self.assertEqual(len(recipe.nodes), 2)

        # look up file path for existence
        with self.subTest("look up file path for existence"):
            data = {
                "nodes": [{
                    "name": "A",
                    "inputs": {"a": "../chefkoch/recipe.json"},
                    "outputs": {"c": "outOfA"},
                    "stepsource": "somesource.py"
                }]
            }
            recipe, err = backbone.jsonToRecipe(data)
            self.assertIsNone(err)
            err, warn = recipe.inputIntegrity()
            self.assertIsNone(err)
            self.assertIsNone(warn)
            self.assertEqual(len(recipe.nodes), 1)


#    #def test_findCircles():
#
#

    def test_recursiveDFS(self):
        # recipe with no loop
        with self.subTest("test 1: recipe with no loop"):
            data = {
                "nodes": [{
                    "name": "A",
                    "inputs": {"a": "flavour.a"},
                    "outputs": {"b": "outOfA"},
                    "stepsource": "somesource.py"
                }, {
                    "name": "B",
                    "inputs": {},
                    "outputs": {"final": "outOfB"},
                    "stepsource": "somesource.py"
                }, {
                    "name": "C",
                    "inputs": {"1": "outOfA", "2": "outOfB"},
                    "outputs": {"c": "outOfC"},
                    "stepsource": "somesource.py"
                }, {
                    "name": "D",
                    "inputs": {"1": "outOfC", "2": "outOfB"},
                    "outputs": {"c": "outOfD"},
                    "stepsource": "somesource.py"
                }]
            }
            recipe, err = backbone.jsonToRecipe(data)
            self.assertIsNone(err)
            result = recipe.findCircles()
            print(result)


class TestFlavour(unittest.TestCase):

    def test_readjson(self):
        # test 1: valid JSON flavour file.
        with self.subTest("test 1: valid JSON flavour file."):
            result, err = backbone.openjson("../flavour.json")
            self.assertIsNone(err)
            self.assertEqual(result['fS'], 9.22e9)
            self.assertEqual(result['subsample'][0]['type'], 'range')
            self.assertEqual(result['average'][2], 64)
            self.assertEqual(result['tx_lfsr_tap'], "0x8F1")
