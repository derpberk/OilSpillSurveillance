import time
from numba.experimental import jitclass
import gym
import numpy as np
import matplotlib.pyplot as plt


class OilSpillEnv():

	def __init__(self, boundaries_map, dt=1, kw=0.5, kc=1, gamma=1, flow=50):

		# Environment parameters

		self.done = None
		self.im0 = None
		self.im1 = None
		self.v = None
		self.u = None
		self.boundaries_map = boundaries_map
		self.x, self.y = np.meshgrid(np.arange(0, self.boundaries_map.shape[0]),
		                             np.arange(0, self.boundaries_map.shape[1]))

		self.visitable_positions = np.column_stack(np.where(self.boundaries_map == 1)).astype(float)

		self.dt = dt
		self.Kw = kw
		self.Kc = kc
		self.gamma = gamma

		self.x_bins = np.arange(0, self.boundaries_map.shape[0]+1)
		self.y_bins = np.arange(0, self.boundaries_map.shape[1]+1)

		# Environment variables
		self.source_points = None
		self.wind_speed = None
		self.source_fuel = None
		self.contamination_position = None
		self.contamination_speed = None
		self.density = None
		self.flow = flow
		self.spill_directions = None

		self.particles_speeds = None

		self.init = False

		self.ax = None
		self.fig = None

	def reset(self):
		"""Reset the env variables"""

		if not self.init:
			self.init = True

		self.done = False

		random_indx = np.random.choice(np.arange(0,len(self.visitable_positions)), np.random.randint(1,3), replace=False)
		self.source_points = np.copy(self.visitable_positions[random_indx])
		self.wind_speed = np.random.rand(2) * 2 - 1
		self.source_fuel = 10000
		self.contamination_position = np.copy(self.source_points)

		x0 = np.random.randint(0, self.boundaries_map.shape[0])
		y0 = np.random.randint(0, self.boundaries_map.shape[1])

		# Current vector field
		self.u = np.sin(np.pi * (self.x - x0) / 50) * np.cos(np.pi * (self.y - y0) / 50)
		self.v = -np.cos(np.pi * (self.x - x0) / 50) * np.sin(np.pi * (self.y - y0) / 50)

		# Density map
		self.density = np.zeros_like(self.boundaries_map)

	def step(self):
		""" Process the action and update the environment state """

		assert self.init, "Environment not initiated!"
		
		# Generate new particles
		for source_point in self.source_points:
			# While there is enough fuel
			if self.source_fuel > 0:
				for _ in range(self.flow):
					
					# Compute the components of the particle movement #
					v_random = self.gamma * (np.random.rand(2) * 2 - 1)
					v_wind = self.Kw * self.wind_speed
					v_current = self.Kc * self.get_current_speed(source_point)
					# Add the new position to the list #
					v_new = source_point + self.dt * (v_wind + v_current) + v_random

					if self.boundaries_map[v_new[0].astype(int),v_new[1].astype(int)] == 0:
						v_new = np.copy(source_point)

					self.contamination_position = np.vstack((self.contamination_position, v_new))
					self.source_fuel -= 1
		
		# Update the particles positions #
		expelled = []
		for i in range(len(self.contamination_position)):

			# Compute the components of the particle movement #
			v_random = self.gamma * (np.random.rand(2) * 2 - 1)
			v_wind = self.Kw * self.wind_speed
			v_current = self.Kc * self.get_current_speed(self.contamination_position[i])
			# Add the new position to the list #
			v_new = self.dt * (v_wind + v_current) + v_random
			new_position = self.contamination_position[i, :] + v_new
			new_position = np.clip(new_position, 0, (self.boundaries_map.shape[0]-1, self.boundaries_map.shape[1]-1))
			# Update the positions #
			if self.boundaries_map[new_position[0].astype(int), new_position[1].astype(int)] == 1:
				if self.density[new_position[0].astype(int), new_position[1].astype(int)] < 50:
					self.contamination_position[i, :] = new_position

			if any(self.contamination_position[i] > self.boundaries_map.shape) or any(self.contamination_position[i] < 0):
				expelled.append(i)

		self.contamination_position = np.delete(self.contamination_position, expelled, axis=0)
		self.density, _, _ = np.histogram2d(self.contamination_position[:, 0], self.contamination_position[:, 1],
		                                    [self.x_bins, self.y_bins])


		return self.density

	def get_current_speed(self, position):
		int_position = position.astype(int)
		return np.array([self.v[int_position[1], int_position[0]], self.u[int_position[1], int_position[0]]])

	def render(self):

		if self.im1 is None:

			self.fig, self.ax = plt.subplots(1, 2, figsize=(10, 5))
			self.ax[0].quiver(self.x, self.y, self.u, self.v, scale=100)
			self.ax[0].set_xlim((0, self.boundaries_map.shape[0]))
			self.ax[0].set_ylim((0, self.boundaries_map.shape[1]))
			self.ax[0].invert_yaxis()
			self.im0 = self.ax[0].scatter(self.contamination_position[:, 0], self.contamination_position[:, 1])
			rendered = np.copy(self.boundaries_map) * self.density
			rendered[self.boundaries_map == 0] = np.nan
			self.im1 = self.ax[1].imshow(rendered, interpolation=None, cmap='jet', vmin=0, vmax=30)

		else:
			rendered = np.copy(self.boundaries_map) * self.density
			rendered[self.boundaries_map == 0] = np.nan
			self.im0.set_offsets(self.contamination_position)
			self.im1.set_data(rendered)

		self.fig.canvas.draw()
		self.fig.canvas.flush_events()
		plt.pause(0.0001)

	def update_to_time(self, t):

		self.reset()

		t0 = time.time()
		for _ in range(t):
			self.step()

		print("Mean time per iteration: ", (time.time()-t0)/t)
		return self.density


if __name__ == '__main__':

	my_map = np.genfromtxt('example_map.csv', delimiter=',')


	env = OilSpillEnv(my_map, dt=0.1, flow = 10, gamma=1, kc = 1, kw=1)
	env.reset()


	for _ in range(1000):
		env.step()
		env.render()

	plt.show()
