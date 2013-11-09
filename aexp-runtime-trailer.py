#-------------------------------------------------------
#  ... and now print out the results

for var in ENV:
    print("%s = %g" % (var, ENV[var]))

# better test that it does what we expect

assert ENV["alpha"] == 3
assert ENV["beta"] == -1
assert ENV["gamma"] == 2
assert ENV["fern"] == 9
assert ENV["ace"] == 45
assert ENV["waldo"] == 12





    
