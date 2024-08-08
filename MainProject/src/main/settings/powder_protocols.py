from powder_settings import PowderProtocol, PowderSettings

default = PowderProtocol(name = "default",
                            tol = 0.2,
                            fast_settings = PowderSettings(
                                opening_deg = 50,
                                percent_target = 0.75,
                                max_growth = 3
                                ),
                            med_settings = PowderSettings(
                                thresh = 5,
                                opening_deg = 30,
                                percent_target = 0.50,
                                max_growth = 1.25,
                                amplitude = 75
                                ),
                            slow_settings = PowderSettings(
                                thresh = 3,
                                opening_deg = 25,
                                percent_target = 1,
                                max_growth = 1.1,
                                shut_valve = False
                                ),
                            ultra_slow_settings = PowderSettings(
                                thresh = 2,
                                opening_deg = 10,
                                percent_target = 0.7,
                                max_growth = 1.1,
                                amplitude = 50,
                                shut_valve = False
                                ),
                             scale_delay=1
                            )

alconox = PowderProtocol(name = "alconox",
                            tol = 0.2,
                            fast_settings = PowderSettings(
                                opening_deg = 40,
                                percent_target = 0.75,
                                max_growth = 3
                                ),
                            med_settings = PowderSettings(
                                thresh = 5,
                                opening_deg = 30,
                                percent_target = 0.50,
                                max_growth = 1.1
                                ),
                            slow_settings = PowderSettings(
                                thresh = 2,
                                opening_deg = 30,
                                percent_target = 1,
                                max_growth = 1.1,
                                shut_valve = False
                                ),
                            ultra_slow_settings = PowderSettings(
                                thresh = 2,
                                opening_deg = 5,
                                percent_target = 0.7,
                                max_growth = 1.1,
                                amplitude = 50,
                                shut_valve = False
                                ),
                             scale_delay=1
                            )
LiOAc = PowderProtocol(name = "LiOAc",
                       tol = 0.2,
                            fast_settings = PowderSettings(
                                opening_deg = 80,
                                percent_target = 0.9,
                                max_growth = 3
                                ),
                            med_settings = PowderSettings(
                                thresh = 50,
                                opening_deg = 70,
                                percent_target = 0.9,
                                max_growth = 1.5
                                ),
                            slow_settings = PowderSettings(
                                thresh = 10,
                                opening_deg = 50,
                                percent_target = 0.8,
                                max_growth = 1.3,
                                amplitude = 70,
                                shut_valve = False
                                ),
                            ultra_slow_settings = PowderSettings(
                                thresh = 2,
                                opening_deg = 40,
                                percent_target = 0.8,
                                max_growth = 1.3,
                                amplitude = 60,
                                shut_valve = False
                                ),
                             scale_delay=1
                            )