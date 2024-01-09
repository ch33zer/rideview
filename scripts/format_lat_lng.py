import sys

if len(sys.argv) != 2:
	print("Provide points")
	sys.exit(1)
points = sys.argv[1]
l = points.split(",")
paired = [(l[i], l[i+1]) for i in range(0, len(l), 2)]
print(',\n'.join(f"{lat},{lon}" for lat,lon in paired))
