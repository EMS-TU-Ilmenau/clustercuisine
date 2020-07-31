"""
The items are the Objects stored in the Fridge

"""
from chefkoch.container import JSONContainer
import chefkoch.core
import chefkoch.tarball
import os
import warnings
import zlib
from abc import ABC, abstractmethod


class Item(ABC):
    """
    An item represent a piece of data, either an input or an output of a step
    """

    def __init__(self, shelf, dict=None, container=None):
        # erstmal vorläufiges dict
        # zugeordneter Shelf
        self.shelf = shelf

        # legt passenden JSON-Container an
        # muss wahrscheinlich nochmal ausgelagert werden
        # self.hashName = zlib.adler32(dict.encode('utf-8'))

        if True:  # falls es ein neuer Container ist self.check()
            self.refLog = JSONContainer()
            self.refLog["test"] = "hua"
            self.hashName = self.refLog.hash()
            self.refLog.save((self.shelf.path + "/" + self.hashName + ".json"))
        else:  # ansonsten neuen Container
            self.refLog = JSONContainer()

        # self.refLog = container

    def createHash(self):
        """
        create a hashfile for the dataset
        """

        pass

    def checkHash(self):
        """
        Check if the hashfile is still valid

        Returns:
        --------
        returns:
            true,....

        """
        pass

    def jsonHash(self, input):
        # wird vermutlich erstmal nicht weiter betrachtet
        """
        makes a hash over the jsonfile, to check if it already exists
        """
        hashName = zlib.adler32(json_object.encode("utf-8"))
        # return str(hashName)
        return None

    def check(self):
        """
        Checks if the file and it's refLog exists and if the refLog itself is
        unchanged

        Returns:
        --------
        returns:
            true,....

        """
        if os.path.isfile(self.shelf.path + "/" + self.hashName + ".json"):
            return True
        else:
            return False


class Result(Item):
    pass


class Resource(Item):
    """
    Resources used to create a specific item
    """

    def __init__(self, basePath):
        pass