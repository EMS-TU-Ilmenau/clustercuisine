import chefkoch.recipe as rcp
import chefkoch.container as cntnr
# flav = rec.readfile('flavour',
# 'flavour.yaml')
recdict = cntnr.YAMLContainer('/mnt/c/Users/makle/PycharmProjects/chefkoch/test2/recipe.yml')

reci = rcp.readrecipe(recdict.data)
# reci = rcp.readfile('recipe',
#                     '/home/maka/PycharmProjects/chefkoch/test/recipe.yaml')
#
# # x = (reci.getPrerequisits(4))
# # x.reverse()
#
# y = rcp.Plan(reci, "prisma_volume", "collect_volume")
#
# # for i in x:
# #     print(i.name)
#
# print(y)
import os
os.system('chef test')