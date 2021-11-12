using System;

namespace My_awesome_program
{
    class program
    {

        static void Main(string[] args)
            {
                double num01;
                double num02;
                double num03;
                double num04;

                Console.Write("input a number: ");

                num01 = Convert.ToDouble( Console.ReadLine());

                Console.Write("Input a second number: ");
                num02 = Convert.ToDouble( Console.ReadLine());

                Console.Write("Input a third number: ");
                num03 = Convert.ToDouble( Console.ReadLine());

                Console.Write("Above numbers will be multiplied, what do you want to divide them with: ");
                num04 = Convert.ToDouble( Console.ReadLine());

                double result = num01 * num02 * num03 / num04;
                Console.WriteLine("The result is " + result);

                //wait before closing
                Console.ReadKey();
            }
    
    }
}