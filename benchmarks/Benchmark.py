import os
import subprocess
import random


class Benchmark(object):

    """
    Defines the benchmark for each input that is required.  These benchmarks have 3 TestCases
    which will help us prioritize the test cases in order to achieve maximum coverage with
    the smallest amount of tests

    It is assumed that each object here has a complimenting ".c" of the name.  Such that
    tcas will have a tcas.c in the same root directory of tcas

    from there we will take each benchmark and run the gcov on it.  This will give us a baseline.

    name: name of program to run
    path: root path + name
    compile: example compilation
    dir: dir for inputs (may contain multiple dirs)
    example: example of running the program
    test_cases: file which contains test cases for us
    mutations: list of mutations to test against, a list of paths which contain
        all available mutations for the benchmark
    results: where to store the coverage results

    the results data structure is as follows:
        results[test_id] = {statements: {coverage={line:True||False}, covered: x, not: x, id: test_id},
                            branches: {coverage={x:[True||False, ...n], covered: x, not: x, id: test_id}}
    """

    """
    This will give us the branch and statement coverage of runs
    we will need to formulate our run as follows:
        gcc -fprofile-arcs -ftest-coverage -fPIC input.c -o out
        This creates 2 files: [exec].gcda and [exec].gcno
        we then execute: ./out [args]
        then run: gcov -abc input.c
        rm input.c.gcov
        and repeat
        from there we can run gcov and see exactly what happens
        gcov -a -b -c -o gcov_out --object-file executable './executable arg1 arg2 argN'"
    """
    __gcc_out = "out"
    __universe = "universe.txt"
    __gcc = "gcc --coverage -fprofile-arcs -ftest-coverage -fPIC -o"
    __gcov_out = "gcov_out"
    __gcov_obj_file = "--object-file executable"
    __gcov = "gcov -bc"

    def __init__(self, path, line):
        b = line.split('~')
        self.name = b[0]
        self.compile = b[1]
        self.example = b[2]
        self.dir = b[3]
        self.test_cases = b[4]
        self.path = path + self.name + "/"
        self.mutations = []
        self.tag = "[Benchmark]\t"
        self.tests = []
        self.mutant_results = {}

        # Compile the file with the necessary gcov flags
        Benchmark.run_command("{0} {1}{2} {3}{4}.c"
                              .format(Benchmark.__gcc, self.path, Benchmark.__gcc_out, self.path, self.name))

        # get all the mutations present in the directory
        for subdirs, dirs, files in os.walk(self.path):
            to_check = subdirs.split('/')[-1]
            if len(to_check) > 0:
                if to_check[0] == 'v':
                    self.mutations.append(subdirs)

        # this is where we will store the results for our tests
        self.results = {}
        # run the tests on our non-mutated program
        self.run_tests()

    """
    Run the tests available to the program
    """
    def run_tests(self):
        x = 0
        print "{0}Beginning to run tests for {1}".format(self.tag, self.name)
        os.chdir(self.path)
        with open(self.path + Benchmark.__universe) as f:
            for line in f:
                self.tests.append(line)
                # run the test set given our newly compiled file
                command = "{0}./{1} {2}".format(self.path, Benchmark.__gcc_out, line)
                Benchmark.run_command(command)

                # Create the .gcov file from the gcno and gcda data
                command = "{0} {1}{2}.c".format(Benchmark.__gcov, self.path, self.name)
                Benchmark.run_command(command)

                # parse the gcov results
                self.parse_gcov("{0}{1}.c.gcov".format(self.path, self.name), x)

                command = "rm {0}{1}.gcno {2}{3}.gcda".format(self.path, self.name, self.path, self.name)
                Benchmark.run_command(command)
                x += 1
                if x > 9:
                    break
                else:
                    continue
        print "{0}size of results: {1}".format(self.tag, len(self.results))

    """
    Parse the gcov output for the branch information
    """
    def parse_gcov(self, path, test_number):
        line_number = 0
        # lets us know whether we are parsing branches or lines
        still_branch = False
        # container for all the branches in a set
        branch = []
        statements = {}
        branches = {}
        branches_covered = []
        branches_not_covered = []
        statements_covered = []
        statements_not_covered = []
        with open(path) as f:
            for line in f:
                split = line.split()
                # Junk or garbage input from gcov
                if split[0] == "-:" or split[0] == "$$$$$:" or split[0] == "function" or "-block" in split[1]:
                    continue

                # If we don't have a branch, parse it as a regular line
                # and add the previous branches to the list
                if split[0] != "branch":
                    # we have a branch and we need to save it, then progress our line number
                    if still_branch:
                        branches[line_number] = branch
                        branch = []
                        still_branch = False
                    # Get the line number and add it to the statements
                    line_number = int(split[1].strip(":}"))
                    statements[line_number] = True if split[0].strip(":") != "#####" else False
                    if statements[line_number] is True:
                        statements_covered.append(line_number)
                    else:
                        statements_not_covered.append(line_number)
                else:
                    if split[3] == "executed" and split[2] == "never":
                        branch.append(False)
                    else:
                        branch.append(True if int(split[3]) > 0 else False)
                    if branch[len(branch) - 1] is True:
                        branches_covered.append(line_number)
                    else:
                        branches_not_covered.append(line_number)
                    still_branch = True
        self.results[test_number] = {'statements': {'coverage': statements,
                                                    'covered': statements_covered, 'not': statements_not_covered,
                                                    'id': test_number, 'covered_count': random.randint(1, 100),
                                                    #'id': test_number, 'covered_count': len(statements_covered),
                                                    'not_count': len(statements_not_covered)},
                                     'branches': {'coverage': branches,
                                                  'covered': branches_covered, 'not': branches_not_covered,
                                                  'id': test_number, 'covered_count': len(branches_covered),
                                                  'not_count': len(branches_not_covered)}}

    """
    Run the different test cases on the mutant programs
    """
    def run_mutation_tests(self, rand, total, additional):
        for mutation in self.mutations:
            os.chdir(mutation)
            # Compile the file with the necessary gcov flags
            command = "{0} {1} {2}.c".format(Benchmark.__gcc, Benchmark.__gcc_out, self.name)
            Benchmark.run_command(command)

            """
            Run the mutants against the test sets I've discovered
            """
            for r in rand:

                # run the test set given our newly compiled file
                command = "./{0} {1}".format(Benchmark.__gcc_out, r)
                Benchmark.run_command(command)

                # Create the .gcov file from the gcno and gcda data
                command = "{0} {1}.c".format(Benchmark.__gcov, self.name)
                Benchmark.run_command(command)

                # parse the gcov results some how...

                self.mutant_results['random'].append("")
                pass
            for t in total:
                # run the test set given our newly compiled file
                command = "./{0} {1}".format(Benchmark.__gcc_out, t)
                Benchmark.run_command(command)

                # Create the .gcov file from the gcno and gcda data
                command = "{0} {1}.c".format(Benchmark.__gcov, self.name)
                Benchmark.run_command(command)

                # parse the gcov results some how...

                self.mutant_results['total'].append("")
                pass
            for a in additional:
                # run the test set given our newly compiled file
                command = "./{0} {1}".format(Benchmark.__gcc_out, t)
                Benchmark.run_command(command)

                # Create the .gcov file from the gcno and gcda data
                command = "{0} {1}.c".format(Benchmark.__gcov, self.name)
                Benchmark.run_command(command)

                # parse the gcov results some how...
                self.mutant_results['additional'].append("")
                pass

        pass
    """
    Retrieve each mutation from the program folder
    This will return a path for all mutations needed
    testing
    """
    def get_mutations_as_string(self):
        string = ""
        for x in self.mutations:
            string = string + "\t" + x
        return string

    """
    wrapper to run a command and capture the output
    """
    @staticmethod
    def run_command(command):
        print(command)
        p = subprocess.Popen(command.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        return out, err

    def __str__(self):
        string = "Name: " + self.name + "\nCompilation: " + self.compile + "\nExample: "
        string = string + self.example + "\nDir: " + self.dir + "\nTest cases: " + self.test_cases
        string = string + "Mutations: " + self.get_mutations_as_string()
        return string + "\n=======================\n"
