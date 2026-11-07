import { createContext, useContext } from 'react'

export const JobContext = createContext(null)

export const useJob = () => useContext(JobContext)
